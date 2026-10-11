<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Tests;
use PHPUnit\Framework\TestCase;
use ThinkPixel\SR\{Document, ThinkPixelSRClient};
use ThinkPixel\SR\Exception\{HTTPError, TimeoutError};

/** Synthetic loopback only; exercises the actual cURL adapter. */
final class GuzzleTransportTest extends TestCase
{
    private $process;
    private string $directory;
    private string $url;
    protected function setUp(): void
    {
        $socket = stream_socket_server('tcp://127.0.0.1:0', $errno, $message);
        if ($socket === false) { self::fail('Loopback binding required'); }
        $address = stream_socket_get_name($socket, false); fclose($socket);
        $this->directory = sys_get_temp_dir().'/thinkpixel-php-test-'.bin2hex(random_bytes(8));
        mkdir($this->directory);
        file_put_contents($this->directory.'/router.php', <<<'ROUTER'
<?php
file_put_contents(__DIR__.'/requests', $_SERVER['REQUEST_URI']."\n", FILE_APPEND);
if ($_SERVER['REQUEST_URI'] === '/auth/token') {
    header('Content-Type: application/json');
    echo json_encode(['token'=>'loopback-jwt','exp'=>time()+900]);
} elseif ($_SERVER['REQUEST_URI'] === '/store') {
    header('Location: /sink', true, 302);
} elseif ($_SERVER['REQUEST_URI'] === '/search') {
    header('Content-Type: application/json');
    usleep(250000);
    echo '{"results":[]}';
} else { echo '{}'; }
ROUTER);
        $this->process = proc_open([PHP_BINARY, '-c', php_ini_loaded_file(), '-S', $address, $this->directory.'/router.php'],
            [0=>['pipe','r'], 1=>['file',$this->directory.'/server.log','a'], 2=>['file',$this->directory.'/server.log','a']], $pipes);
        self::assertIsResource($this->process);
        fclose($pipes[0]);
        $this->url = 'http://'.$address;
        for ($attempt=0; $attempt<100; $attempt++) {
            $ready = @stream_socket_client('tcp://'.$address, $errno, $message, 0.02);
            if ($ready !== false) { fclose($ready); return; }
            usleep(10000);
        }
        self::fail('Local test server failed to start');
    }
    protected function tearDown(): void
    {
        if (is_resource($this->process)) { proc_terminate($this->process); proc_close($this->process); }
        if (isset($this->directory)) { foreach (glob($this->directory.'/*') as $file) { unlink($file); } rmdir($this->directory); }
    }
    private function client(float $timeout=1.0): ThinkPixelSRClient
    { return new ThinkPixelSRClient(['base_url'=>$this->url, 'api_key'=>'loopback-key', 'allow_insecure_localhost'=>true, 'timeout'=>$timeout]); }
    public function testDefaultTransportDoesNotFollowRedirects(): void
    {
        $client = $this->client();
        try { $client->store([new Document(1,'local')]); self::fail(); }
        catch (HTTPError $error) { self::assertSame(302, $error->http_status); }
        finally { $client->close(); }
        self::assertSame("/auth/token\n/store\n", file_get_contents($this->directory.'/requests'));
    }
    public function testDefaultTransportEnforcesTimeoutAndDoesNotRetry(): void
    {
        $client = $this->client(0.05); $client->authenticate();
        $started = hrtime(true);
        try { $client->search('local'); self::fail(); }
        catch (TimeoutError $error) {
            self::assertNull($error->http_status); self::assertNull($error->getPrevious());
            self::assertLessThan(0.2,(hrtime(true)-$started)/1e9);
        } finally { $client->close(); }
        self::assertSame("/auth/token\n/search\n", file_get_contents($this->directory.'/requests'));
    }
}
