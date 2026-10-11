<?php
declare(strict_types=1);
require dirname(__DIR__) . '/vendor/autoload.php';
use ThinkPixel\SR\ThinkPixelSRClient;
use ThinkPixel\SR\Exception\ThinkPixelSRError;
$baseUrl = getenv('THINKPIXEL_BASE_URL');
if ($baseUrl === false || $baseUrl === '') { throw new RuntimeException('Set THINKPIXEL_BASE_URL'); }
$client = new ThinkPixelSRClient(['base_url' => $baseUrl]);
try {
    $result = $client->search('How does asynchronous ingestion work?');
    echo count($result->results) . " results\n";
} catch (ThinkPixelSRError $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(1);
} finally { $client->close(); }
