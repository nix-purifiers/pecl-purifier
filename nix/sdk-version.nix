{
  lib,
  nixpkgsSrc,
  php,
}:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    version = php.version;
    source = toString php.unwrapped.src;
    zts = php.unwrapped.ztsSupport;
    debug = builtins.any (flag: lib.hasPrefix "--enable-debug" flag) php.unwrapped.configureFlags;
    adapter = builtins.hashFile "sha256" ../pecl_purifier/patch-sdk.py;
  }
)
