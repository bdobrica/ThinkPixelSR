<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
final readonly class SearchHit extends ValueObject
{
    /** @param array<string, mixed> $extensions */
    public function __construct(public int $id, #[\SensitiveParameter] public string $text,
        public float $score, #[\SensitiveParameter] public array $extensions = []) {}
    public function toArray(): array
    { return array_merge($this->extensions, ['id' => $this->id, 'text' => $this->text, 'score' => $this->score]); }
}
