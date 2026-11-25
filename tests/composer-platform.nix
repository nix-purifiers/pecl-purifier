{
  pkgs,
  projection,
  originalPhp,
  testProgram,
}:
let
  php = projection.php;
  composer = "${originalPhp.packages.composer}/share/php/composer/bin/composer";
  declarations = pkgs.writeText "pecl-projection-modules.json" (
    builtins.toJSON (
      map (module: {
        name = module.extensionName;
        path = "${module}/lib/php/extensions/${module.extensionName}.so";
      }) projection.closure
    )
  );
in
pkgs.runCommand "pecl-composer-platform-consumer" { } ''
  mkdir -p "$out" "$TMPDIR/home"
  export HOME="$TMPDIR/home" COMPOSER_HOME="$TMPDIR/composer"
  export COMPOSER_DISABLE_NETWORK=1
  cat > composer.json <<'JSON'
  {"name":"proof/pecl-native","require":{"ext-purifierproof":"0.1.0","ext-yaml":"2.3.0","ext-msgpack":"3.0.1"},"repositories":[{"packagist.org":false}]}
  JSON
  ${php}/bin/php ${composer} update --no-install --no-interaction > "$out/capture.log" 2>&1
  ${php}/bin/php ${composer} check-platform-reqs --lock > "$out/platform.log"
  ${php}/bin/php ${testProgram} > "$out/native.txt"
  grep -qx 42 "$out/native.txt"
  ${php}/bin/php -r '
    $maps = file_get_contents("/proc/self/maps");
    $rows = json_decode(file_get_contents($argv[1]), true, flags: JSON_THROW_ON_ERROR);
    foreach ($rows as $row) {
      $path = realpath($row["path"]);
      if (!extension_loaded($row["name"]) || $path === false || !str_contains($maps, $path))
        throw new RuntimeException("Unexpected native module origin: ".$row["name"]);
      echo $row["name"], "\t", phpversion($row["name"]), "\t", hash_file("sha256", $path), "\n";
    }
  ' ${declarations} > "$out/modules.tsv"
  if ${originalPhp}/bin/php ${composer} check-platform-reqs --lock > "$out/negative.log" 2>&1; then
    echo "Composer accepted an absent extension" >&2
    exit 1
  fi
  grep -F ext-purifierproof "$out/negative.log" | grep -F missing
  cp composer.lock "$out/"
''
