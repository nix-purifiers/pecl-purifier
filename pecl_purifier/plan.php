<?php
require_once __DIR__ . '/native-common.php';
require_once 'PEAR/Frontend.php';
require_once 'PEAR/Command.php';
require_once 'Console/Getopt.php';
$config = purifier_configure($argv[1]);
PEAR_Command::setFrontendType('CLI');
PEAR_Command::getCommands();
$parsed = Console_Getopt::getopt2(array_slice($argv, 3), 'vqh?V');
if (PEAR::isError($parsed)) throw new Exception($parsed->getMessage());
[$global, $rest] = $parsed;
$command = $rest[0] ?? 'help';
$shortcuts = PEAR_Command::getShortcuts();
$command = $shortcuts[$command] ?? $command;
$options = $params = $packages = [];
if (!in_array($command, ['help', 'version'])) {
    $native = PEAR_Command::factory($command, $config);
    if (PEAR::isError($native)) throw new Exception($native->getMessage());
    $short = $long = null;
    PEAR_Command::getGetoptArgs($command, $short, $long);
    $parsed = Console_Getopt::getopt2(array_slice($rest, 1), $short, $long);
    if (PEAR::isError($parsed)) throw new Exception($parsed->getMessage());
    [$found, $params] = $parsed;
    foreach ($found as [$option, $value]) {
        $value = $value ?? true;
        if (strlen($option) == 1) {
            foreach ($native->getOptions($command) as $name=>$definition) {
                if (($definition['shortopt'] ?? null) == $option) $options[$name] = $value;
            }
        } else {
            $options[ltrim($option, '-')] = $value;
        }
    }
    $registry = $config->getRegistry();
    foreach ($params as $value) {
        if (file_exists($value)) {
            $packages[] = null;
        } else {
            $package = $registry->parsePackageName($value, 'pecl.php.net');
            $packages[] = PEAR::isError($package) ? null : $package;
        }
    }
}
file_put_contents($argv[2], json_encode(['command'=>$command,'global'=>$global,'options'=>$options,'params'=>$params,'packages'=>$packages], JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES));
