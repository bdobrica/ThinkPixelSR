<?php
declare(strict_types=1);
namespace ThinkPixel\SR;
use ThinkPixel\SR\Exception\ValidationError;
final readonly class Document extends ValueObject
{
    /** @param array<string, string>|null $extra */
    public function __construct(
        public int $id,
        #[\SensitiveParameter] public string $text,
        public ?string $language = null,
        #[\SensitiveParameter] public ?array $extra = null,
    ) {
        if ($id < -2147483648 || $id > 2147483647) { throw new ValidationError('store'); }
        if ($extra !== null) {
            foreach ($extra as $key => $value) {
                if (!is_string($key) || !is_string($value)) { throw new ValidationError('store'); }
            }
        }
    }
    public function toArray(): array
    {
        $data = ['id' => $this->id, 'text' => $this->text];
        if ($this->language !== null) { $data['language'] = $this->language; }
        if ($this->extra !== null) { $data['extra'] = (object) $this->extra; }
        return $data;
    }
}
