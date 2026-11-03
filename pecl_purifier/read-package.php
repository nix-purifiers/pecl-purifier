<?php
require_once __DIR__ . '/native-common.php';
$config = purifier_configure($argv[3]);
$metadata = purifier_metadata(purifier_package($config, $argv[1]));
file_put_contents($argv[2], json_encode($metadata, JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES));
