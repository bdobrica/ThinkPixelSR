<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
final readonly class SearchResult extends ValueObject
{
    /**
     * @param list<SearchHit> $results
     * @param array<string, mixed> $extensions
     */
    public function __construct(#[\SensitiveParameter] public array $results,
        #[\SensitiveParameter] public array $extensions = []) {}
    public function toArray(): array
    { return array_merge($this->extensions, ['results' => array_map(fn(SearchHit $hit) => $hit->toArray(), $this->results)]); }
}
