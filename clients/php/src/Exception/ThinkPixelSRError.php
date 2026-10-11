<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Exception;

class ThinkPixelSRError extends \RuntimeException implements \JsonSerializable
{
    public function __construct(
        public readonly string $operation,
        public readonly ?int $http_status = null,
        public readonly string $delivery_state = 'not_sent',
    ) {
        parent::__construct((new \ReflectionClass($this))->getShortName() . ': ' . $operation);
    }
    /** @return array<string, mixed> */
    public function jsonSerialize(): array
    {
        return ['name' => static::class, 'operation' => $this->operation,
            'http_status' => $this->http_status, 'delivery_state' => $this->delivery_state];
    }
    /** @return array<string, mixed> */
    public function __debugInfo(): array { return $this->jsonSerialize(); }
    public function __toString(): string { return $this->getMessage(); }
    /** @return array<string, mixed> */
    public function __serialize(): array { return $this->jsonSerialize(); }
}
