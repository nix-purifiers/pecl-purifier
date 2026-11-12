{
  lib,
  runCommand,
  fetchurl,
  python3,
  writeText,
  php,
  nativePear,
  purifier,
  sdkVersion,
  buildPecl,
}:
{
  lock,
  fetchers ? { },
  extensionOverrides ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  data = checked.data;
  helpers = ../../pecl_purifier;
  tree = purifier.tree (
    {
      name = "pecl-fixed-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchurl
        python3
        writeText
        ;
    }
    // fetchers
  );
  expectedAbi = writeText "pecl-abi.json" (builtins.toJSON data.abi);
  modules = builtins.listToAttrs (
    map (
      node:
      let
        base =
          if builtins.hasAttr node.name php.extensions then
            php.extensions.${node.name}
          else
            buildPecl {
              pname = node.name;
              version = node.native.version;
              src = tree + "/${node.entry}";
            };
        prepared = base.overrideAttrs (old: {
          name = "purified-php-${node.name}-${node.native.version}";
          version = node.native.version;
          src = tree + "/${node.entry}";
          outputs = [
            "out"
            "dev"
          ];
          makeFlags = (old.makeFlags or [ ]) ++ [ "phpincludedir=$(dev)/include" ];
          nativeBuildInputs =
            (old.nativeBuildInputs or [ ])
            ++ nativeBuildInputs
            ++ [
              python3
              php
            ];
          buildInputs = (old.buildInputs or [ ]) ++ map (name: modules.${name}) node.dependencies;
          preConfigure =
            (old.preConfigure or "")
            + "\n"
            + ''
              export PECL_PURIFIER_FROZEN=1
              ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/phpize-meta.php "$TMPDIR/abi.json" ${php.unwrapped.dev}/bin/phpize > "$TMPDIR/abi.log"
              ${python3}/bin/python3 ${helpers}/check-metadata.py ${expectedAbi} "$TMPDIR/abi.json"
              ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/read-package.php "$src" "$TMPDIR/package.json" "$TMPDIR/pecl-state"
              ${python3}/bin/python3 ${helpers}/check-metadata.py ${writeText "pecl-package.json" (builtins.toJSON node.native)} "$TMPDIR/package.json"
            '';
          meta = (old.meta or { }) // {
            broken = false;
          };
        });
        final =
          if builtins.hasAttr node.name extensionOverrides then
            prepared.overrideAttrs extensionOverrides.${node.name}
          else
            prepared;
      in
      {
        name = node.name;
        value = final;
      }
    ) data.nodes
  );
  manifest = writeText "pecl-environment.json" (
    builtins.toJSON {
      abi = data.abi;
      nodes = map (node: {
        inherit (node) name native;
        archive = "${tree}/${node.entry}";
        module = "${modules.${node.name}}/lib/php/extensions/${node.native.extension}.so";
        headers = toString modules.${node.name}.dev;
      }) data.nodes;
    }
  );
  output =
    runCommand "pecl-locked-environment"
      {
        nativeBuildInputs = [
          php
          python3
        ];
      }
      ''
            mkdir -p "$out"
            cp ${manifest} "$out/manifest.json"
            cp ${php}/lib/php.ini "$out/php.ini"
        chmod u+w "$out/php.ini"
            ${python3}/bin/python3 -c 'import json,os;d=json.load(open("${manifest}"));f=open(os.environ["out"]+"/php.ini","a");f.write("\n");[f.write(("zend_extension" if n["native"]["type"]=="zendextsrc" else "extension")+"="+n["module"]+"\n") for n in d["nodes"]]'
            PHP_INI_SCAN_DIR= ${php.unwrapped}/bin/php -c "$out/php.ini" -r '$d=json_decode(file_get_contents($argv[1]),true);foreach($d["nodes"] as $n){if(!extension_loaded($n["native"]["extension"])||phpversion($n["native"]["extension"])!==$n["native"]["version"])throw new Exception("Native PHP module identity differs from lock");}' "$out/manifest.json"
      '';
in
assert checked.problems == [ ];
assert lib.assertMsg (data.sdk == sdkVersion) "PHP SDK changed; update the lock";
{
  inherit output modules tree;
}
