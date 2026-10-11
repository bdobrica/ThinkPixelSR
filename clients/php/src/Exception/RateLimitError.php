<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Exception;

class RateLimitError extends HTTPError
{
    public ?float $retry_after_seconds = null;
}
