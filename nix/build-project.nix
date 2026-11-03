{
  lib,
  runCommand,
  fetchurl,
  python3,
  writeText,
  writeShellScript,
  php,
  nativePear,
  purifier,
  sdkVersion,
  buildPecl,
  gnutar,
  gzip,
}@scope:
{
  src,
  lockFile ? src + "/pecl-purifier.lock.json",
  fetchers ? { },
  extensionOverrides ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "php test.php",
  buildCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  prepared =
    import ./environment.nix
      (builtins.removeAttrs scope [
        "writeShellScript"
        "gnutar"
        "gzip"
      ])
      {
        inherit
          lock
          fetchers
          extensionOverrides
          nativeBuildInputs
          ;
      };
  environment = prepared.output;
  helpers = ../pecl_purifier;
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".pecl-purifier"
        "result"
        "__pycache__"
      ]);
  };
  expected = writeText "pecl-project.json" (builtins.toJSON lock.data.project);
  expectedAbi = writeText "pecl-project-abi.json" (builtins.toJSON lock.data.abi);
  configuredPhp = writeShellScript "pecl-project-php" ''
    export PHP_INI_SCAN_DIR=""
    exec ${php.unwrapped}/bin/php -c ${environment}/php.ini ${
      lib.optionalString (
        lock.data.project != null
      ) ''-d extension="$PWD/modules/${lock.data.project.extension}.so"''
    } "$@"
  '';
  validate = ''
    export PECL_PURIFIER_FROZEN=1
    ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/phpize-meta.php "$TMPDIR/abi.json" ${php.unwrapped.dev}/bin/phpize > "$TMPDIR/abi.log"
    ${python3}/bin/python3 ${helpers}/check-metadata.py ${expectedAbi} "$TMPDIR/abi.json"
    ${lib.optionalString (lock.data.project != null) ''
      ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/read-package.php "$PWD/package.xml" "$TMPDIR/project.json" "$TMPDIR/pecl-state"
      ${python3}/bin/python3 ${helpers}/check-metadata.py ${expected} "$TMPDIR/project.json"
    ''}
  '';
  checks = ''
    mkdir -p runner
    ln -s ${configuredPhp} runner/php
    export PATH="$PWD/runner:$PATH"
    ${checkCommand}
  '';
  project =
    if lock.data.project != null then
      (buildPecl {
        pname = lock.data.project.name;
        version = lock.data.project.version;
        src = source;
        outputs = [
          "out"
          "dev"
        ];
        makeFlags = [ "phpincludedir=$(dev)/include" ];
        nativeBuildInputs = [
          python3
          php
        ]
        ++ nativeBuildInputs;
        preConfigure = validate;
        inherit doCheck;
      }).overrideAttrs
        (_: {
          checkPhase = checks;
        })
    else
      runCommand "pecl-php-application"
        {
          nativeBuildInputs = [
            php
            python3
          ]
          ++ nativeBuildInputs;
        }
        ''
          export HOME="$TMPDIR/home"
          mkdir -p "$HOME" "$out/source"
          cp -pr ${source}/. "$out/source/"
          chmod -R u+w "$out/source"
          cd "$out/source"
          ${validate}
          mkdir runner
          ln -s ${configuredPhp} runner/php
          export PATH="$PWD/runner:$PATH"
          ${buildCommand}
          ${lib.optionalString doCheck checkCommand}
          cp ${environment}/php.ini "$out/php.ini"
        '';
  release =
    runCommand "pecl-native-release"
      {
        nativeBuildInputs = [
          php
          python3
          gnutar
          gzip
        ];
      }
      ''
        export HOME="$TMPDIR/home" PECL_PURIFIER_FROZEN=1
        mkdir -p "$HOME" "$out" source state
        cp -pr ${source}/. source/
        chmod -R u+w source
        ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/phpize-meta.php "$TMPDIR/abi.json" ${php.unwrapped.dev}/bin/phpize > "$TMPDIR/abi.log"
        ${python3}/bin/python3 ${helpers}/check-metadata.py ${expectedAbi} "$TMPDIR/abi.json"
        ${
          if lock.data.project != null then
            ''
              ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${helpers}/read-package.php "$PWD/source/package.xml" "$TMPDIR/project.json" "$PWD/state"
              ${python3}/bin/python3 ${helpers}/check-metadata.py ${expected} "$TMPDIR/project.json"
              export SOURCE_DATE_EPOCH=$(${python3}/bin/python3 -c 'import datetime,json;d=json.load(open("${expected}"));print(int(datetime.datetime.fromisoformat(d["date"]+"T"+(d["time"] or "00:00:00")+"+00:00").timestamp()))')
              package_xml="$PWD/source/package.xml"
              config="$PWD/state/pearrc"
              system_config="$PWD/state/systemrc"
              cd "$out"
              ${php}/bin/php -d error_reporting=8191 -d include_path=${nativePear}/lib/php ${nativePear}/lib/php/peclcmd.php -c "$config" -C "$system_config" package "$package_xml"
            ''
          else
            ''
              tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/php-source.tar.gz" -C source .
            ''
        }
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg (lock.data.sdk == sdkVersion) "PHP SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project environment;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
