<?php
declare(strict_types=1);
namespace ThinkPixel\SR;

/** Payloads are available explicitly through toArray(), never through diagnostics. */
abstract readonly class ValueObject implements \JsonSerializable
{
    /** @return array<string, mixed> */
    abstract public function toArray(): array;
    /** @return array<string, string> */
    final public function __debugInfo(): array { return ['type' => static::class]; }
    /** @return array<string, string> */
    final public function jsonSerialize(): array { return $this->__debugInfo(); }
    /** @return array<string, string> */
    final public function __serialize(): array { return $this->__debugInfo(); }
}
