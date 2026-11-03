<?php
require_once __DIR__ . '/native-common.php';
require_once 'PEAR/Frontend.php';
require_once 'PEAR/Downloader.php';
$config = purifier_configure($argv[1]);
$ui = PEAR_Frontend::singleton('CLI');
$downloader = new PEAR_Downloader($ui, ['onlyreqdeps'=>true], $config);
$packages = $downloader->download(array_slice($argv, 3));
if (PEAR::isError($packages)) throw new Exception($packages->getMessage());
$errors = array_values(array_filter($downloader->getErrorMsgs()));
if ($errors) throw new Exception(json_encode($errors));
$nodes = [];
foreach ($packages as $package) {
    $file = $package->getPackageFile();
    $node = purifier_metadata($file);
    $download = $package->getDownloadURL();
    $node['file'] = $file->getArchiveFile();
    $node['url'] = $download['url'] ?? null;
    $nodes[] = $node;
}
file_put_contents($argv[2], json_encode($nodes, JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES));
