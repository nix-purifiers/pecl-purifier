{ lib }:
{
  src,
  lockFile ? src + "/pecl-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  safe =
    s: builtins.isString s && s != "." && s != ".." && builtins.match "[A-Za-z0-9_.+-]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  native =
    n:
    builtins.isAttrs n
    && safe (n.name or null)
    && safe (n.version or null)
    && (n.channel or null) == "pecl.php.net"
    && builtins.elem (n.type or null) [
      "extsrc"
      "zendextsrc"
    ]
    && builtins.isString (n.extension or null)
    && builtins.match "[A-Za-z0-9_]+" n.extension != null
    && n ? dependencies
    && (builtins.isAttrs n.dependencies || n.dependencies == false || n.dependencies == null)
    && builtins.isString (n.date or null)
    && n ? time
    && (builtins.isString n.time || n.time == false || n.time == null);
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "pecl"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.abi or null)
    && builtins.isString (data.abi.php or null)
    && builtins.isBool (data.abi.zts or null)
    && builtins.isBool (data.abi.debug or null)
    && builtins.isAttrs (data.abi.modules or null)
    && builtins.all (k: builtins.isString data.abi.modules.${k} || data.abi.modules.${k} == false) (
      builtins.attrNames data.abi.modules
    )
    && builtins.all (k: builtins.isInt (data.abi.${k} or null) && data.abi.${k} > 0) [
      "php_api"
      "zend_mod_api"
      "zend_ext_api"
    ]
    && builtins.isList (data.requirements or null)
    && builtins.all builtins.isString data.requirements
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null)
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          (lib.optional (builtins.pathExists (src + "/package.xml")) "package.xml") ++ data.extraInputs
        )
      )
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs data.inputs.${name}
      && builtins.isString (data.inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && (builtins.readDir (dirOf (src + "/${name}"))).${baseNameOf name} == "regular"
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" data.inputs.${name}.content == data.inputs.${name}.sha256
    ) (builtins.attrNames data.inputs)
    && data ? project
    && (data.project == null) == (!(data.inputs ? "package.xml"))
    && (data.project == null || native data.project)
    && builtins.isList nodes
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && native (n.native or null)
      && n.native.name == n.name
      && (n.entry or null) == "archives/${n.name}/${n.native.version}.tgz"
      && builtins.isList (n.dependencies or null)
      && builtins.all (d: builtins.any (other: other.name == d) nodes) n.dependencies
      && builtins.any (e: e.path == n.entry) entries
    ) nodes
    && builtins.length nodes == builtins.length entries
    && builtins.length (lib.unique (map (n: n.name) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (n: n.native.extension) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries;
in
{
  purifier = "pecl";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "PECL lock is missing, stale, or unsupported; run pecl-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
