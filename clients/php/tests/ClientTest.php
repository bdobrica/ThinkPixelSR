<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Tests;
use GuzzleHttp\Psr7\Response;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Psr\Http\Message\{RequestInterface, ResponseInterface};
use ThinkPixel\SR\{Document, ThinkPixelSRClient};
use ThinkPixel\SR\Transport\DeadlineTransport;
use ThinkPixel\SR\Exception\{AuthenticationError, ConfigurationError, HTTPError, PermissionError,
    ProtocolError, RateLimitError, ServerError, StoreFailedError, ThinkPixelSRError, TimeoutError, TransportError, ValidationError};

final class MockTransport implements DeadlineTransport
{
    public array $requests = [];
    public array $budgets = [];
    public function __construct(public array $queue) {}
    public function send(#[\SensitiveParameter] RequestInterface $request, float $timeout): ResponseInterface
    {
        $this->requests[] = $request;
        $this->budgets[] = $timeout;
        $next = array_shift($this->queue);
        if ($next instanceof \Throwable) { throw $next; }
        if (is_callable($next)) { return $next($request, $timeout); }
        if (!$next instanceof ResponseInterface) { throw new \RuntimeException('mock exhausted'); }
        return $next;
    }
}
final class ClientTest extends TestCase
{
    private function auth(string $token = 'synthetic-jwt'): Response
    { return new Response(200, [], json_encode(['token' => $token, 'exp' => time() + 900])); }
    private function response(string $fixture, int $status = 200): Response
    { return new Response($status, [], file_get_contents(__DIR__ . '/../../contracts/fixtures/' . $fixture . '.response.json')); }
    private function client(MockTransport $transport, array $extra = []): ThinkPixelSRClient
    { return new ThinkPixelSRClient(array_merge(['base_url' => 'https://gateway.example/prefix/', 'api_key' => 'synthetic-key', 'transport' => $transport], $extra)); }
    public function testWireCacheAndRedaction(): void
    {
        $transport = new MockTransport([$this->auth(), $this->response('store-accepted', 202), $this->response('search-success')]);
        $client = $this->client($transport);
        $store = $client->store([new Document(900001, 'first', extra: ['kind' => 'example']), new Document(900002, 'second')]);
        self::assertSame('accepted', $store->delivery_state);
        self::assertSame(202, $store->http_status);
        self::assertSame([900001, 900002], $store->pending_ids);
        $search = $client->search('question');
        self::assertNotEmpty($search->results);
        self::assertCount(3, $transport->requests);
        $auth = $transport->requests[0];
        self::assertSame('POST', $auth->getMethod());
        self::assertSame('https://gateway.example/prefix/auth/token', (string) $auth->getUri());
        self::assertSame('synthetic-key', $auth->getHeaderLine('X-API-Key'));
        self::assertSame('', (string) $auth->getBody());
        self::assertFalse($auth->hasHeader('Content-Type'));
        self::assertFalse($auth->hasHeader('Authorization'));
        self::assertSame('Bearer synthetic-jwt', $transport->requests[1]->getHeaderLine('Authorization'));
        self::assertFalse($transport->requests[1]->hasHeader('X-API-Key'));
        self::assertSame('[{"id":900001,"text":"first","extra":{"kind":"example"}},{"id":900002,"text":"second"}]', (string) $transport->requests[1]->getBody());
        self::assertSame('{"text":"question","language":"auto"}', (string) $transport->requests[2]->getBody());
        ob_start(); var_dump($client, $store, $search); $dump = ob_get_clean();
        self::assertStringNotContainsString('synthetic-key', $dump);
        self::assertStringNotContainsString('synthetic-jwt', serialize($client));
        self::assertStringNotContainsString('first', json_encode($store));
        self::assertSame('first', json_decode((string) $transport->requests[1]->getBody())[0]->text);
    }
    #[DataProvider('fixtureCases')]
    public function testSharedFixtures(string $fixture, string $operation, int $status): void
    {
        $transport = new MockTransport([$this->auth(), $this->response($fixture, $status)]);
        $client = $this->client($transport);
        if ($status === 500) {
            try { $client->store([new Document(1, 'x')]); self::fail(); }
            catch (StoreFailedError $error) {
                self::assertSame('failed', $error->delivery_state);
                self::assertSame(2, $error->getResult()->failed_documents);
                self::assertStringNotContainsString('sanitized queue', serialize($error));
            }
        } else {
            $result = $operation === 'store' ? $client->store([new Document(1, 'x')]) : $client->search('question');
            self::assertEquals(json_decode(file_get_contents(__DIR__ . '/../../contracts/fixtures/' . $fixture . '.response.json'), true), json_decode(json_encode($result->toArray()), true));
        }
        self::assertCount(2, $transport->requests);
    }
    public static function fixtureCases(): array
    { return [['store-accepted','store',202], ['store-partial','store',202], ['store-all-failed','store',500], ['search-success','search',200], ['search-empty-qdrant','search',200], ['search-empty-redis','search',200]]; }
    public function test401ReplaysIdenticalBodyOnlyOnceAndClearsFinalToken(): void
    {
        $transport = new MockTransport([$this->auth(), new Response(401, [], 'private'), $this->auth('new-jwt'), new Response(401), $this->auth('third-jwt'), $this->response('search-empty-qdrant')]);
        $client = $this->client($transport);
        try { $client->store([new Document(1, 'sensitive')]); self::fail(); }
        catch (AuthenticationError $error) { self::assertSame('rejected', $error->delivery_state); }
        self::assertCount(4, $transport->requests);
        self::assertSame((string) $transport->requests[1]->getBody(), (string) $transport->requests[3]->getBody());
        self::assertSame('Bearer new-jwt', $transport->requests[3]->getHeaderLine('Authorization'));
        $client->search('question');
        self::assertCount(6, $transport->requests);
    }
    public function testExplicitAuthenticationAlwaysReplacesToken(): void
    {
        $transport = new MockTransport([$this->auth(), $this->auth('replacement'), $this->response('search-empty-qdrant')]);
        $client = $this->client($transport);
        self::assertGreaterThan(time(), $client->authenticate()->exp);
        $client->authenticate(); $client->search('question');
        self::assertSame('Bearer replacement', $transport->requests[2]->getHeaderLine('Authorization'));
    }
    #[DataProvider('statusCases')]
    public function testStatusMappingNoRetry(int $status, string $class, string $delivery): void
    {
        $transport = new MockTransport([$this->auth(), new Response($status, [], 'private server failure')]);
        try { $this->client($transport)->store([new Document(1, 'payload')]); self::fail(); }
        catch (ThinkPixelSRError $error) {
            self::assertInstanceOf($class, $error); self::assertSame($status, $error->http_status);
            self::assertSame($delivery, $error->delivery_state); self::assertNull($error->getPrevious());
            self::assertStringNotContainsString('private', (string) $error);
            self::assertStringNotContainsString('payload', serialize($error));
        }
        self::assertCount(2, $transport->requests);
    }
    public static function statusCases(): array
    { return [[400,ValidationError::class,'rejected'],[422,ValidationError::class,'unknown'],[403,PermissionError::class,'rejected'],[408,TimeoutError::class,'unknown'],[429,RateLimitError::class,'unknown'],[500,ServerError::class,'unknown'],[503,ServerError::class,'unknown'],[302,HTTPError::class,'unknown'],[200,ProtocolError::class,'unknown']]; }
    #[DataProvider('retryCases')]
    public function testRetryAfter(string $header, ?float $expected): void
    {
        $transport = new MockTransport([$this->auth(), new Response(429, ['Retry-After' => $header])]);
        try { $this->client($transport)->search('question'); self::fail(); }
        catch (RateLimitError $error) { self::assertSame($expected, $error->retry_after_seconds); }
        self::assertCount(2, $transport->requests);
    }
    public static function retryCases(): array { return [['10',10.0],['-1',null],['nonsense',null],['',null],['Wed, 01 Jan 2020 00:00:00 GMT',0.0]]; }
    #[DataProvider('badSearch')]
    public function testBadSearch(string $body): void
    {
        $transport = new MockTransport([$this->auth(), new Response(200, [], $body)]);
        $this->expectException(ProtocolError::class); $this->client($transport)->search('x');
    }
    public static function badSearch(): array
    { return [['not json'],['[]'],['{}'],['{"results":null}'],['{"results":{}}'],['{"results":[{"id":true,"text":"x","score":1}]}'],['{"results":[{"id":9223372036854775808,"text":"x","score":1}]}'],['{"results":[{"id":1,"text":null,"score":1}]}'],['{"results":[{"id":1,"text":"x","score":"1"}]}'],['{"results":[{"id":1,"text":"x","score":1e999}]}']]; }
    #[DataProvider('badStore')]
    public function testBadStore(string $field, mixed $value): void
    {
        $data = json_decode((string) $this->response('store-accepted',202)->getBody(), true);
        $data[$field] = $value;
        $transport = new MockTransport([$this->auth(), new Response(202, [], json_encode($data))]);
        try { $this->client($transport)->store([new Document(1,'x')]); self::fail(); }
        catch (ProtocolError $error) { self::assertSame('unknown', $error->delivery_state); }
        self::assertCount(2, $transport->requests);
    }
    public static function badStore(): array
    { return [['received_texts',true],['failed_documents',-1],['pending_documents',0],['pending_ids',null],['pending_ids',[1]],['pending_ids',[1,true]],['failed_items',null],['timestamp','2030-02-30T00:00:00Z'],['timestamp','2030-01-01T24:00:00Z'],['timestamp','2030-01-01'],['timestamp','2030-01-01T00:00:00+99:00']]; }
    #[DataProvider('badAuth')]
    public function testBadAuth(array $data): void
    {
        $transport = new MockTransport([new Response(200, [], json_encode($data))]);
        $this->expectException(ProtocolError::class); $this->client($transport)->authenticate();
    }
    public static function badAuth(): array
    { return [[[]],[['token'=>'','exp'=>4102444800]],[['token'=>"a\nb",'exp'=>4102444800]],[['token'=>'x','exp'=>true]],[['token'=>'x','exp'=>0]],[['token'=>'x','exp'=>4102444800.5]],[['token'=>'x','exp'=>time()+30]]]; }
    public function testUnknownMetadataAndDuplicateIds(): void
    {
        $transport = new MockTransport([$this->auth(), new Response(200, [], '{"future":{"private":"hidden"},"results":[{"id":1,"text":"sensitive","score":0.1,"future":"hidden"},{"id":1,"text":"second","score":0.2}]}')]);
        $result = $this->client($transport)->search('x');
        self::assertSame([1,1], array_column($result->results,'id'));
        self::assertSame('hidden', $result->results[0]->extensions['future']);
        self::assertSame('hidden', $result->extensions['future']->private);
        self::assertStringNotContainsString('hidden', json_encode($result));
        self::assertSame('sensitive',$result->toArray()['results'][0]['text']);
    }
    #[DataProvider('badConfig')]
    public function testBadConfiguration(array $options): void
    { $this->expectException(ConfigurationError::class); $this->client(new MockTransport([]), $options); }
    public static function badConfig(): array
    { return [[['base_url'=>'http://remote.example','allow_insecure_localhost'=>true]],[['base_url'=>'http://127.1','allow_insecure_localhost'=>true]],[['base_url'=>'https://user:pass@example.com']],[['base_url'=>'https://example.com?']],[['base_url'=>'https://example.com#']],[['base_url'=>'https://example.com/path?x=1']],[['base_url'=>"https://example.com/\n"]],[['base_url'=>'https://example.com\\path']],[['api_key'=>'']],[['api_key'=>null]],[['api_key'=>"a\nb"]],[['timeout'=>0]],[['timeout'=>-1]],[['timeout'=>true]],[['timeout'=>INF]],[['timeout'=>NAN]],[['timeout'=>2147484]],[['transport'=>null]],[['unsupported'=>true]]]; }
    public function testEnvironmentKeyAndExplicitPrecedence(): void
    {
        $old = getenv('THINKPIXEL_API_KEY'); putenv('THINKPIXEL_API_KEY=environment-key');
        try {
            $transport = new MockTransport([$this->auth(), $this->auth()]);
            (new ThinkPixelSRClient(['base_url'=>'https://example.com','transport'=>$transport]))->authenticate();
            $this->client($transport)->authenticate();
            self::assertSame('environment-key',$transport->requests[0]->getHeaderLine('X-API-Key'));
            self::assertSame('synthetic-key',$transport->requests[1]->getHeaderLine('X-API-Key'));
            putenv('THINKPIXEL_API_KEY');
            $this->expectException(ConfigurationError::class);
            new ThinkPixelSRClient(['base_url'=>'https://example.com','transport'=>$transport]);
        } finally { putenv($old === false ? 'THINKPIXEL_API_KEY' : 'THINKPIXEL_API_KEY='.$old); }
    }
    public function testLiteralHttpOptIn(): void
    {
        foreach (['localhost','127.0.0.1','[::1]'] as $host) {
            $transport = new MockTransport([$this->auth()]);
            $this->client($transport, ['base_url'=>'http://'.$host.':8080/prefix','allow_insecure_localhost'=>true])->authenticate();
            self::assertSame('http://'.$host.':8080/prefix/auth/token', (string) $transport->requests[0]->getUri());
        }
    }
    #[DataProvider('badDocuments')]
    public function testInvalidDocuments(array $documents): void
    { $transport = new MockTransport([]); $this->expectException(ValidationError::class); $this->client($transport)->store($documents); }
    public static function badDocuments(): array { return [[[]],[[['id'=>1,'text'=>'x']]],[[1=>new Document(1,'x')]]]; }
    public function testDocumentIdAndExtraValidation(): void
    {
        self::assertSame(-2147483648, (new Document(-2147483648,''))->id);
        self::assertSame('{}', json_encode((new Document(2147483647,'', '', []))->toArray()['extra']));
        $this->expectException(ValidationError::class); new Document(2147483648,'x');
    }
    public function testEmptySearchIsLocal(): void
    { $this->expectException(ValidationError::class); $this->client(new MockTransport([]))->search(''); }
    public function testTransportFailureSanitizedAndNotRetried(): void
    {
        $transport = new MockTransport([$this->auth(), new \RuntimeException('synthetic-key payload')]);
        try { $this->client($transport)->store([new Document(1,'x')]); self::fail(); }
        catch (TransportError $error) {
            self::assertSame('unknown',$error->delivery_state); self::assertNull($error->getPrevious());
            self::assertStringNotContainsString('synthetic-key',(string) $error);
            self::assertStringNotContainsString('synthetic-key',serialize($error));
        }
        self::assertCount(2,$transport->requests);
    }
    public function testSharedDeadlineIncludesExchange(): void
    {
        $transport = new MockTransport([function() { usleep(20000); return $this->auth(); }, $this->response('search-empty-qdrant')]);
        $this->client($transport,['timeout'=>0.2])->search('x');
        self::assertLessThan($transport->budgets[0]-0.01,$transport->budgets[1]);
    }
    public function testLateAdapterResponseIsTimeoutWithoutReplay(): void
    {
        $transport = new MockTransport([$this->auth(), function() { usleep(30000); return new Response(401); }]);
        try { $this->client($transport,['timeout'=>0.02])->store([new Document(1,'x')]); self::fail(); }
        catch (TimeoutError $error) { self::assertSame('unknown',$error->delivery_state); }
        self::assertCount(2,$transport->requests);
    }
    public function testExpirySkewTriggersReplacement(): void
    {
        $transport = new MockTransport([new Response(200,[],json_encode(['token'=>'first','exp'=>time()+32])), $this->auth('replacement'), $this->response('search-empty-qdrant')]);
        $client = $this->client($transport); $client->authenticate(); usleep(2100000); $client->search('x');
        self::assertCount(3,$transport->requests);
        self::assertSame('Bearer replacement',$transport->requests[2]->getHeaderLine('Authorization'));
    }
    public function testFailedExplicitExchangeInvalidatesCache(): void
    {
        $transport = new MockTransport([$this->auth(), new Response(500), $this->auth('replacement'), $this->response('search-empty-qdrant')]);
        $client = $this->client($transport); $client->authenticate();
        try { $client->authenticate(); self::fail(); } catch (ServerError $error) { self::assertSame(500,$error->http_status); }
        $client->search('x');
        self::assertCount(4,$transport->requests);
        self::assertSame('Bearer replacement',$transport->requests[3]->getHeaderLine('Authorization'));
    }
    public function testInvalidExtraMapIsLocal(): void
    { $this->expectException(ValidationError::class); new Document(1,'x',extra:['key'=>1]); }
    public function testMalformedUtf8IsLocal(): void
    { $this->expectException(ValidationError::class); $this->client(new MockTransport([]))->store([new Document(1,"\xff")]); }
    public function testCloseIsIdempotentAndDoesNotCloseCallerAdapter(): void
    {
        $transport = new MockTransport([$this->auth()]); $client = $this->client($transport);
        $client->close(); $client->close();
        self::assertCount(1,$transport->queue);
        $this->expectException(ConfigurationError::class); $client->authenticate();
    }
}
