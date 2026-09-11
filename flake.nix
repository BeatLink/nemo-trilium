{
    description = "Save files from Nemo's right-click menu into Trilium";

    inputs = {
        nixpkgs = {
            url = "github:NixOS/nixpkgs/nixos-unstable";
        };
    };

    outputs =
        { self, nixpkgs }:
        let
            systems = [
                "x86_64-linux"
                "aarch64-linux"
            ];
            forAllSystems = nixpkgs.lib.genAttrs systems;
            pkgsFor = system: nixpkgs.legacyPackages.${system};
        in
        {
            packages = forAllSystems (
                system:
                let
                    pkgs = pkgsFor system;
                in
                {
                    nemo-trilium = pkgs.callPackage ./package.nix { };
                    default = self.packages.${system}.nemo-trilium;
                }
            );

            # A shell for running the command straight out of the checkout, without building it.
            devShells = forAllSystems (
                system:
                let
                    pkgs = pkgsFor system;
                in
                {
                    default = pkgs.mkShell {
                        packages = [
                            pkgs.gtk3
                            pkgs.gobject-introspection
                            pkgs.libnotify
                            pkgs.xdg-utils
                            (pkgs.python3.withPackages (ps: [
                                ps.pygobject3
                                ps.markdown
                            ]))
                        ];
                    };
                }
            );

            checks = forAllSystems (system: {
                build = self.packages.${system}.nemo-trilium;
            });

            overlays = {
                default = final: _prev: { nemo-trilium = final.callPackage ./package.nix { }; };
            };

            homeManagerModules = {
                nemo-trilium = import ./home-manager.nix self;
                default = self.homeManagerModules.nemo-trilium;
            };

            formatter = forAllSystems (
                system:
                let
                    pkgs = pkgsFor system;
                in
                pkgs.writeShellScriptBin "nixfmt-4" ''exec ${pkgs.nixfmt}/bin/nixfmt --indent 4 "$@"''
            );
        };
}
