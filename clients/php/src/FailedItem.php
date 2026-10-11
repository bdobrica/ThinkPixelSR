<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
final readonly class FailedItem extends ValueObject
{
    /** @param array<string, mixed> $extensions */
    public function __construct(public int $id, #[\SensitiveParameter] public string $error,
        #[\SensitiveParameter] public array $extensions = []) {}
    public function toArray(): array
    { return array_merge($this->extensions, ['id' => $this->id, 'error' => $this->error]); }
}
