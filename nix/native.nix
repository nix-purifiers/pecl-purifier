{
  runCommand,
  php,
  python3,
}:
runCommand "pecl-purifier-native" { nativeBuildInputs = [ python3 ]; } ''
  mkdir -p "$out/lib/php"
  cp -pr ${php.unwrapped}/lib/php/. "$out/lib/php/"
  chmod -R u+w "$out/lib/php"
  cd "$out/lib/php"
  python3 ${../pecl_purifier/patch-sdk.py}
''
