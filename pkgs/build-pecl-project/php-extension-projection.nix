{ lib, php }:
{
  project,
  modules,
  lock,
}:
let
  nodes = lib.listToAttrs (map (node: lib.nameValuePair node.name node) lock.nodes);
  locked = lib.mapAttrs (
    name: module:
    module
    // {
      extensionName = nodes.${name}.native.extension;
      peclDeps = map (dependency: locked.${dependency}) nodes.${name}.dependencies;
      zendExtension = nodes.${name}.native.type == "zendextsrc";
    }
  ) modules;
  extension = project // {
    extensionName = lock.project.extension;
    peclDeps = builtins.attrValues locked;
    zendExtension = lock.project.type == "zendextsrc";
  };
  closure = [ extension ] ++ builtins.attrValues locked;
  names = map (module: module.extensionName) closure;
  applyTo =
    target:
    assert lib.assertMsg (
      target.unwrapped.drvPath == php.unwrapped.drvPath
    ) "The PECL projection requires the exact PHP SDK that built its extension";
    target.withExtensions (
      { enabled, ... }:
      (builtins.filter (module: !(builtins.elem module.extensionName names)) enabled) ++ closure
    );
in
assert lib.assertMsg (
  lib.unique names == names
) "Duplicate PECL extension names in the locked closure";
{
  inherit extension closure applyTo;
  php = applyTo php;
  inherit (lock) abi;
  platformRequirement = "ext-${lib.toLower extension.extensionName}";
}
