{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  php,
  nativePear,
  toolchain,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "pecl-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/pecl-purifier"
    cp -r pecl_purifier nix "$out/lib/pecl-purifier/"
    install -m755 bin/pecl-purifier "$out/bin/pecl-purifier"
    substituteInPlace "$out/lib/pecl-purifier/nix/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/pecl-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default PECL_PURIFIER_GH ${gh}/bin/gh \
      --set PECL_PURIFIER_BOOTSTRAP_PHP ${php}/bin/php \
      --set PECL_PURIFIER_RUNTIME_PHP ${php.unwrapped}/bin/php \
      --set PECL_PURIFIER_ORIGINAL_PHP ${php}/bin/php \
      --set PECL_PURIFIER_ORIGINAL_PECL ${php.unwrapped}/bin/pecl \
      --set PECL_PURIFIER_NATIVE_PEAR ${nativePear} \
      --set PECL_PURIFIER_PHPIZE ${php.unwrapped.dev}/bin/phpize \
      --set PECL_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set PECL_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/pecl-purifier" "$out/bin/php" --add-flags '--native=php'
    makeWrapper "$out/bin/pecl-purifier" "$out/bin/pecl" --add-flags '--native=pecl'
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native PECL and PHP with locked Nix-resolved extensions";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "pecl-purifier";
  };
}
