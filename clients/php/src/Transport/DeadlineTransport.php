<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Transport;
use Psr\Http\Message\RequestInterface;
use Psr\Http\Message\ResponseInterface;

/** Caller-owned adapters must enforce the remaining budget, TLS, no redirect/retry,
 * and fully buffer the body before returning. PSR-18 alone cannot ensure this. */
interface DeadlineTransport
{
    public function send(#[\SensitiveParameter] RequestInterface $request, float $timeout): ResponseInterface;
}
