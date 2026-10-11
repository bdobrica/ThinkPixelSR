<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Transport;
use GuzzleHttp\Client;
use GuzzleHttp\Exception\ConnectException;
use GuzzleHttp\Exception\RequestException;
use GuzzleHttp\Handler\CurlHandler;
use Psr\Http\Message\RequestInterface;
use Psr\Http\Message\ResponseInterface;
use ThinkPixel\SR\Exception\TimeoutError;
use ThinkPixel\SR\Exception\TransportError;

/** Fixed cURL handler: no user middleware, retry, redirect or TLS override. */
final class GuzzleTransport implements DeadlineTransport
{
    private ?Client $client;
    public function __construct()
    {
        if (!extension_loaded('curl')) { throw new TransportError('configure'); }
        $this->client = new Client(['handler' => new CurlHandler()]);
    }
    public function send(#[\SensitiveParameter] RequestInterface $request, float $timeout): ResponseInterface
    {
        if ($this->client === null) { throw new TransportError('closed'); }
        try {
            return $this->client->send($request, ['timeout' => $timeout, 'connect_timeout' => $timeout,
                'allow_redirects' => false, 'http_errors' => false, 'verify' => true, 'stream' => false]);
        } catch (ConnectException | RequestException $error) {
            if (($error->getHandlerContext()['errno'] ?? null) === 28) { throw new TimeoutError('transport'); }
            throw new TransportError('transport');
        } catch (\Throwable) { throw new TransportError('transport'); }
    }
    public function close(): void { $this->client = null; }
    /** @return array<string, string> */
    public function __debugInfo(): array { return ['type' => self::class]; }
    /** @return array<string, string> */
    public function __serialize(): array { return $this->__debugInfo(); }
}
