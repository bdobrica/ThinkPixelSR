<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
final readonly class AuthResult extends ValueObject
{
    public function __construct(public int $exp) {}
    public function toArray(): array { return ['exp' => $this->exp]; }
}
