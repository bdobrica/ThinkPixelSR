<?php
declare(strict_types=1);
namespace ThinkPixel\SR\Exception;
use ThinkPixel\SR\StoreResult;

class StoreFailedError extends ServerError
{
    public function __construct(#[\SensitiveParameter] private readonly StoreResult $result)
    { parent::__construct('store', 500, 'failed'); }
    public function getResult(): StoreResult { return $this->result; }
}
