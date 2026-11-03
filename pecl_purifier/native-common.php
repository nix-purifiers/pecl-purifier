<?php
error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);
require_once 'PEAR.php';
require_once 'PEAR/Config.php';
require_once 'PEAR/PackageFile.php';

function purifier_configure($state) {
    if (!is_dir($state)) mkdir($state, 0700, true);
    $state = realpath($state);
    $config = PEAR_Config::singleton($state . '/pearrc', $state . '/systemrc');
    foreach (['php_dir'=>'php', 'cache_dir'=>'cache', 'download_dir'=>'downloads',
              'temp_dir'=>'tmp', 'ext_dir'=>'extensions', 'bin_dir'=>'bin',
              'doc_dir'=>'docs', 'data_dir'=>'data', 'test_dir'=>'tests',
              'cfg_dir'=>'config', 'man_dir'=>'man', 'www_dir'=>'www'] as $key=>$leaf) {
        $directory = $state . '/' . $leaf;
        if ($key === 'temp_dir' && getenv('PECL_PURIFIER_BUILD_TEMP')) {
            $directory = getenv('PECL_PURIFIER_BUILD_TEMP');
        }
        if (!is_dir($directory)) mkdir($directory, 0700, true);
        foreach (['pear.php.net', 'pecl.php.net'] as $channel) {
            if (!$config->set($key, $directory, 'user', $channel) && $config->get($key, null, $channel) !== $directory) {
                throw new Exception('Cannot configure native PECL path ' . $key);
            }
        }
    }
    $config->set('default_channel', 'pecl.php.net');
    $config->set('preferred_state', 'stable');
    $config->set('auto_discover', 0);
    $result = $config->store();
    if (PEAR::isError($result)) throw new Exception($result->getMessage());
    return $config;
}

function purifier_metadata($package) {
    return ['name'=>$package->getPackage(), 'channel'=>$package->getChannel(),
            'version'=>$package->getVersion(), 'type'=>$package->getPackageType(),
            'state'=>$package->getState(),
            'extension'=>$package->getProvidesExtension(),
            'dependencies'=>$package->getDeps(true),
            'date'=>$package->getDate(), 'time'=>$package->getTime()];
}

function purifier_package($config, $path) {
    $factory = new PEAR_PackageFile($config);
    $package = $factory->fromAnyFile($path, PEAR_VALIDATE_NORMAL);
    if (PEAR::isError($package)) throw new Exception($package->getMessage());
    return $package;
}
