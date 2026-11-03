<?php
error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);
require_once 'PEAR.php';
require_once 'PEAR/Frontend.php';
require_once 'PEAR/Builder.php';
$ui=PEAR_Frontend::singleton('CLI');
$builder=new PEAR_Builder('', $ui);
exec(escapeshellarg($argv[2]).' --version',$lines,$status);
if ($status!==0) throw new Exception('native phpize failed');
foreach ($lines as $line) $builder->phpizeCallback('cmdoutput',$line);
$result=['php'=>PHP_VERSION,'zts'=>PHP_ZTS,'debug'=>PHP_DEBUG,'php_api'=>$builder->php_api_version,'zend_mod_api'=>$builder->zend_module_api_no,'zend_ext_api'=>$builder->zend_extension_api_no];
$modules=[];
foreach (get_loaded_extensions() as $extension) $modules[$extension]=phpversion($extension);
ksort($modules);
$result['modules']=$modules;
if (!$result['php_api'] || !$result['zend_mod_api'] || !$result['zend_ext_api']) throw new Exception('native PHP ABI metadata unavailable');
file_put_contents($argv[1],json_encode($result,JSON_PRETTY_PRINT));
