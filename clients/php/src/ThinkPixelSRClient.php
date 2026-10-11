<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
use GuzzleHttp\Psr7\HttpFactory;
use Psr\Http\Message\RequestFactoryInterface;
use Psr\Http\Message\StreamFactoryInterface;
use Psr\Http\Message\ResponseInterface;
use ThinkPixel\SR\Exception\{AuthenticationError, ConfigurationError, HTTPError, PermissionError,
    ProtocolError, RateLimitError, ServerError, StoreFailedError, TimeoutError, TransportError, ValidationError};
use ThinkPixel\SR\Transport\{DeadlineTransport, GuzzleTransport};

/** Synchronous client; do not share concurrently across fibers/threads. */
final class ThinkPixelSRClient implements \JsonSerializable
{
    public const VERSION = '0.1.0';
    private readonly string $baseUrl;
    private readonly string $apiKey;
    private readonly float $timeout;
    private readonly DeadlineTransport $transport;
    private readonly bool $ownsTransport;
    private readonly RequestFactoryInterface $requestFactory;
    private readonly StreamFactoryInterface $streamFactory;
    private ?string $token = null;
    private int $exp = 0;
    private bool $closed = false;

    /** @param array<string, mixed> $options */
    public function __construct(#[\SensitiveParameter] array $options)
    {
        if (PHP_INT_SIZE !== 8 || array_diff(array_keys($options), ['base_url', 'api_key', 'timeout',
            'transport', 'allow_insecure_localhost', 'request_factory', 'stream_factory']) !== []) {
            throw new ConfigurationError('configure');
        }
        $url = $options['base_url'] ?? null;
        $local = array_key_exists('allow_insecure_localhost', $options) ? $options['allow_insecure_localhost'] : false;
        if (!is_string($url) || !is_bool($local) || preg_match('/[\x00-\x20\x7f\\\\]/', $url)
            || !preg_match('~^(https?)://([^/?#]+)(/[^?#]*)?$~D', $url, $match)) {
            throw new ConfigurationError('configure');
        }
        $parsed = parse_url($url);
        if ($parsed === false || !isset($parsed['host']) || isset($parsed['user']) || isset($parsed['pass'])
            || str_contains($match[2], '@') || ($match[1] === 'http' && (!$local
                || !preg_match('/^(localhost|127\.0\.0\.1|\[::1\])(:[0-9]+)?$/D', $match[2])))) {
            throw new ConfigurationError('configure');
        }
        $key = array_key_exists('api_key', $options) ? $options['api_key'] : getenv('THINKPIXEL_API_KEY');
        if (!is_string($key) || !preg_match('/^[\x21-\x7e]+$/D', $key)) { throw new ConfigurationError('configure'); }
        $timeout = array_key_exists('timeout', $options) ? $options['timeout'] : 15.0;
        if ((!is_int($timeout) && !is_float($timeout)) || !is_finite((float) $timeout)
            || $timeout <= 0 || $timeout > 2147483.647) { throw new ConfigurationError('configure'); }
        if (array_key_exists('transport', $options) && !$options['transport'] instanceof DeadlineTransport) {
            throw new ConfigurationError('configure');
        }
        $factory = new HttpFactory();
        $requestFactory = array_key_exists('request_factory', $options) ? $options['request_factory'] : $factory;
        $streamFactory = array_key_exists('stream_factory', $options) ? $options['stream_factory'] : $factory;
        if (!$requestFactory instanceof RequestFactoryInterface || !$streamFactory instanceof StreamFactoryInterface) {
            throw new ConfigurationError('configure');
        }
        $this->baseUrl = rtrim($url, '/');
        $this->apiKey = $key;
        $this->timeout = (float) $timeout;
        $this->ownsTransport = !isset($options['transport']);
        $this->transport = $options['transport'] ?? new GuzzleTransport();
        $this->requestFactory = $requestFactory;
        $this->streamFactory = $streamFactory;
    }
    /** @return array<string, string> */
    public function __debugInfo(): array { return ['type' => self::class]; }
    /** @return array<string, string> */
    public function jsonSerialize(): array { return $this->__debugInfo(); }
    /** @return array<string, string> */
    public function __serialize(): array { return $this->__debugInfo(); }
    public function close(): void
    {
        $this->closed = true;
        $this->token = null;
        $this->exp = 0;
        if ($this->ownsTransport && $this->transport instanceof GuzzleTransport) { $this->transport->close(); }
    }
    private function deadline(): float
    {
        if ($this->closed) { throw new ConfigurationError('closed'); }
        return hrtime(true) / 1e9 + $this->timeout;
    }
    private function remaining(float $deadline, string $operation, string $delivery): float
    {
        $left = $deadline - hrtime(true) / 1e9;
        if ($left < 0.001) { throw new TimeoutError($operation, null, $delivery); }
        return $left;
    }
    private function send(string $operation, float $deadline, #[\SensitiveParameter] ?string $body,
        string $delivery): ResponseInterface
    {
        $budget = $this->remaining($deadline, $operation, $operation === 'store' ? 'not_sent' : $delivery);
        try {
            $request = $this->requestFactory->createRequest('POST', $this->baseUrl . '/' . ($operation === 'authenticate' ? 'auth/token' : $operation))
                ->withHeader('Accept', 'application/json');
            if ($operation === 'authenticate') { $request = $request->withHeader('X-API-Key', $this->apiKey); }
            else {
                $request = $request->withHeader('Authorization', 'Bearer ' . $this->token)
                    ->withHeader('Content-Type', 'application/json')->withBody($this->streamFactory->createStream($body ?? ''));
            }
        } catch (\Throwable) { throw new TransportError($operation, null, 'not_sent'); }
        $budget = $this->remaining($deadline, $operation, 'not_sent');
        try { $response = $this->transport->send($request, $budget); }
        catch (TimeoutError) { throw new TimeoutError($operation, null, $delivery); }
        catch (\Throwable) { throw new TransportError($operation, null, $delivery); }
        $this->remaining($deadline, $operation, $delivery);
        return $response;
    }
    private function discard(#[\SensitiveParameter] ResponseInterface $response): void
    {
        try { $response->getBody()->close(); } catch (\Throwable) { /* Cleanup must not expose adapter exceptions. */ }
    }
    private function status(#[\SensitiveParameter] ResponseInterface $response, string $operation, int $expected): void
    {
        $status = $response->getStatusCode();
        if ($status === $expected) { return; }
        $delivery = $operation === 'store' ? (in_array($status, [400, 401, 403], true) ? 'rejected' : 'unknown') : 'not_sent';
        $class = match (true) {
            $status === 400 || $status === 422 => ValidationError::class,
            $status === 401 => AuthenticationError::class,
            $status === 403 => PermissionError::class,
            $status === 408 => TimeoutError::class,
            $status === 429 => RateLimitError::class,
            $status >= 500 => ServerError::class,
            $status >= 200 && $status < 300 => ProtocolError::class,
            default => HTTPError::class,
        };
        $error = new $class($operation, $status, $delivery);
        if ($error instanceof RateLimitError) {
            $value = $response->getHeaderLine('Retry-After');
            if (preg_match('/^[0-9]+$/D', $value)) {
                $number = (float) $value;
                $error->retry_after_seconds = is_finite($number) ? $number : null;
            } elseif (preg_match('/^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), /', $value)) {
                $date = \DateTimeImmutable::createFromFormat('D, d M Y H:i:s \G\M\T', $value, new \DateTimeZone('UTC'));
                if ($date !== false && $date->format('D, d M Y H:i:s \G\M\T') === $value) {
                    $error->retry_after_seconds = (float) max(0, $date->getTimestamp() - time());
                }
            }
        }
        throw $error;
    }
    private function json(#[\SensitiveParameter] ResponseInterface $response, string $operation, float $deadline): \stdClass
    {
        $delivery = $operation === 'store' ? 'unknown' : 'not_sent';
        try { $body = $response->getBody()->getContents(); }
        catch (TimeoutError) { throw new TimeoutError($operation, $response->getStatusCode(), $delivery); }
        catch (\Throwable) { throw new TransportError($operation, $response->getStatusCode(), $delivery); }
        $this->remaining($deadline, $operation, $delivery);
        try { $data = json_decode($body, false, 512, JSON_THROW_ON_ERROR); }
        catch (\JsonException) { throw new ProtocolError($operation, $response->getStatusCode(), $delivery); }
        if (!$data instanceof \stdClass) { throw new ProtocolError($operation, $response->getStatusCode(), $delivery); }
        return $data;
    }
    private function exchange(float $deadline): AuthResult
    {
        $this->token = null;
        $this->exp = 0;
        $response = $this->send('authenticate', $deadline, null, 'not_sent');
        try {
            $this->status($response, 'authenticate', 200);
            $data = $this->json($response, 'authenticate', $deadline);
            if (!isset($data->token, $data->exp) || !is_string($data->token)
                || !preg_match('/^[\x21-\x7e]+$/D', $data->token) || !is_int($data->exp) || $data->exp <= time() + 30) {
                throw new ProtocolError('authenticate', 200);
            }
            $this->token = $data->token;
            $this->exp = $data->exp;
            return new AuthResult($this->exp);
        } finally { $this->discard($response); }
    }
    public function authenticate(): AuthResult { return $this->exchange($this->deadline()); }
    private function request(string $operation, #[\SensitiveParameter] string $body, float $deadline): ResponseInterface
    {
        if ($this->token === null || $this->exp <= time() + 30) { $this->exchange($deadline); }
        $response = $this->send($operation, $deadline, $body, $operation === 'store' ? 'unknown' : 'not_sent');
        if ($response->getStatusCode() === 401) {
            $this->discard($response);
            $this->token = null;
            $this->exp = 0;
            $this->exchange($deadline);
            $response = $this->send($operation, $deadline, $body, $operation === 'store' ? 'unknown' : 'not_sent');
            if ($response->getStatusCode() === 401) { $this->token = null; $this->exp = 0; }
        }
        return $response;
    }
    /** @param list<Document> $documents */
    public function store(#[\SensitiveParameter] array $documents): StoreResult
    {
        if ($documents === [] || !array_is_list($documents)) { throw new ValidationError('store'); }
        foreach ($documents as $document) { if (!$document instanceof Document) { throw new ValidationError('store'); } }
        try { $body = json_encode(array_map(fn(Document $doc) => $doc->toArray(), $documents), JSON_THROW_ON_ERROR); }
        catch (\JsonException) { throw new ValidationError('store'); }
        $deadline = $this->deadline();
        $response = $this->request('store', $body, $deadline);
        try {
            if ($response->getStatusCode() === 500) {
                try { $result = $this->storeResult($this->json($response, 'store', $deadline), 500); }
                catch (ProtocolError) { throw new ServerError('store', 500, 'unknown'); }
                throw new StoreFailedError($result);
            }
            $this->status($response, 'store', 202);
            return $this->storeResult($this->json($response, 'store', $deadline), 202);
        } finally { $this->discard($response); }
    }
    public function search(#[\SensitiveParameter] string $text, string $language = 'auto'): SearchResult
    {
        if ($text === '') { throw new ValidationError('search'); }
        try { $body = json_encode(['text' => $text, 'language' => $language], JSON_THROW_ON_ERROR); }
        catch (\JsonException) { throw new ValidationError('search'); }
        $deadline = $this->deadline();
        $response = $this->request('search', $body, $deadline);
        try {
            $this->status($response, 'search', 200);
            $data = $this->json($response, 'search', $deadline);
            if (!isset($data->results) || !is_array($data->results)) { throw new ProtocolError('search', 200); }
            $hits = [];
            foreach ($data->results as $hit) {
                if (!$hit instanceof \stdClass || !isset($hit->id, $hit->text, $hit->score) || !is_int($hit->id)
                    || !is_string($hit->text) || (!is_int($hit->score) && !is_float($hit->score)) || !is_finite((float) $hit->score)) {
                    throw new ProtocolError('search', 200);
                }
                $hits[] = new SearchHit($hit->id, $hit->text, (float) $hit->score, $this->extensions($hit, ['id', 'text', 'score']));
            }
            return new SearchResult($hits, $this->extensions($data, ['results']));
        } finally { $this->discard($response); }
    }
    /**
     * @param list<string> $known
     * @return array<string, mixed>
     */
    private function extensions(#[\SensitiveParameter] \stdClass $data, array $known): array
    { return array_diff_key(get_object_vars($data), array_flip($known)); }
    private function storeResult(#[\SensitiveParameter] \stdClass $data, int $status): StoreResult
    {
        $invalid = fn() => new ProtocolError('store', $status, 'unknown');
        foreach (['received_texts', 'pending_documents', 'failed_documents'] as $field) {
            if (!isset($data->$field) || !is_int($data->$field) || $data->$field < 0) { throw $invalid(); }
        }
        if ($data->received_texts === 0 || $data->pending_documents + $data->failed_documents !== $data->received_texts
            || ($status === 202 && $data->pending_documents === 0) || ($status === 500 && $data->pending_documents !== 0)
            || !isset($data->timestamp) || !is_string($data->timestamp) || !$this->validTimestamp($data->timestamp)) { throw $invalid(); }
        $pending = null;
        if (property_exists($data, 'pending_ids')) {
            if (!is_array($data->pending_ids) || !array_is_list($data->pending_ids) || count($data->pending_ids) !== $data->pending_documents) { throw $invalid(); }
            foreach ($data->pending_ids as $id) { if (!is_int($id)) { throw $invalid(); } }
            $pending = $data->pending_ids;
        }
        $failed = null;
        if (property_exists($data, 'failed_items')) {
            if (!is_array($data->failed_items) || count($data->failed_items) !== $data->failed_documents) { throw $invalid(); }
            $failed = [];
            foreach ($data->failed_items as $item) {
                if (!$item instanceof \stdClass || !isset($item->id, $item->error) || !is_int($item->id) || !is_string($item->error)) { throw $invalid(); }
                $failed[] = new FailedItem($item->id, $item->error, $this->extensions($item, ['id', 'error']));
            }
        }
        return new StoreResult($data->received_texts, $data->pending_documents, $data->failed_documents, $data->timestamp,
            $status, $status === 202 ? 'accepted' : 'failed', $pending, $failed,
            $this->extensions($data, ['received_texts', 'pending_documents', 'failed_documents', 'timestamp', 'pending_ids', 'failed_items']));
    }
    private function validTimestamp(#[\SensitiveParameter] string $value): bool
    {
        if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-])(\d{2}):(\d{2}))$/D', $value, $parts)) { return false; }
        return checkdate((int) $parts[2], (int) $parts[3], (int) $parts[1])
            && (int) $parts[4] < 24 && (int) $parts[5] < 60 && (int) $parts[6] < 60
            && (!isset($parts[10], $parts[11]) || ((int) $parts[10] < 24 && (int) $parts[11] < 60));
    }
}
