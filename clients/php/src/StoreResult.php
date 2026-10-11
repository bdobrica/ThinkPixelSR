<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
final readonly class StoreResult extends ValueObject
{
    /**
     * @param list<int>|null $pending_ids
     * @param list<FailedItem>|null $failed_items
     * @param array<string, mixed> $extensions
     */
    public function __construct(public int $received_texts, public int $pending_documents,
        public int $failed_documents, public string $timestamp, public int $http_status,
        public string $delivery_state, #[\SensitiveParameter] public ?array $pending_ids = null,
        #[\SensitiveParameter] public ?array $failed_items = null,
        #[\SensitiveParameter] public array $extensions = []) {}
    public function toArray(): array
    {
        $data = array_merge($this->extensions, ['received_texts' => $this->received_texts,
            'pending_documents' => $this->pending_documents, 'failed_documents' => $this->failed_documents,
            'timestamp' => $this->timestamp]);
        if ($this->pending_ids !== null) { $data['pending_ids'] = $this->pending_ids; }
        if ($this->failed_items !== null) { $data['failed_items'] = array_map(fn(FailedItem $item) => $item->toArray(), $this->failed_items); }
        return $data;
    }
}
