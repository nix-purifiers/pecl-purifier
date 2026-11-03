{
  description = "Locked, Nix-resolved PECL extensions";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        pecl-purifier = final.lib.makeScope final.newScope (scope: {
          nativePear = scope.callPackage ./nix/native.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          buildPecl = scope.callPackage (nixpkgs + "/pkgs/build-support/php/build-pecl.nix") {
            php = final.php.unwrapped;
          };
          sdkVersion = import ./nix/sdk-version.nix {
            nixpkgsSrc = nixpkgs;
            inherit (final) lib php;
          };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildPeclProject = scope.callPackage ./nix/build-project.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).pecl-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/pecl-purifier";
          meta.description = "Lock native PHP extensions";
        };
      });
      lib.pecl-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.pecl-purifier.buildPeclProject {
            src = ./examples/minimal;
            doCheck = true;
          };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
