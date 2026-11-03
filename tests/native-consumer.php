<?php
error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);
require_once 'PEAR/Config.php';
require_once 'PEAR/Frontend.php';
require_once 'PEAR/Builder.php';
$reflection = new ReflectionClass('PEAR_Builder');
if (str_contains($reflection->getFileName(), 'pecl-purifier-native')) {
    throw new Exception('Consumer must use the original native PEAR SDK');
}
$config = PEAR_Config::singleton($argv[1] . '/pearrc', $argv[1] . '/systemrc');
$ui = PEAR_Frontend::singleton('CLI');
$builder = new PEAR_Builder('', $ui);
$built = $builder->build(realpath($argv[2]));
if (PEAR::isError($built)) throw new Exception($built->getMessage());
if (!is_dir($argv[3])) mkdir($argv[3], 0700, true);
foreach ($built as $file) {
    if (str_ends_with($file['file'], '.so')) {
        copy($file['file'], $argv[3] . '/' . basename($file['file']));
    }
}
