{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  php = pkgs.php;
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativePear = pkgs.callPackage ./native.nix { inherit php; };
  buildPecl = pkgs.callPackage (nixpkgsSrc + "/pkgs/build-support/php/build-pecl.nix") {
    php = php.unwrapped;
  };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc php;
    inherit (pkgs) lib;
  };
  build =
    pkgs.callPackage ./build-project.nix
      {
        inherit
          php
          purifier
          nativePear
          buildPecl
          sdkVersion
          ;
      }
      {
        src = /. + project;
        lockFile = /. + companion;
      };
  output =
    if target == "environment" then
      build.packages.environment
    else if target == "release" then
      build.release
    else
      throw "Unknown PECL target";
in
if profile then
  pkgs.writeText "pecl-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output
