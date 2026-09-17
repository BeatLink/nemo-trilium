self:
{
    config,
    lib,
    pkgs,
    ...
}:

let
    cfg = config.programs.nemo-trilium;

    render =
        value:
        if builtins.isBool value then (if value then "true" else "false") else builtins.toString value;

    settingsFile = lib.generators.toINI { mkKeyValue = key: value: "${key} = ${render value}"; } {
        trilium = cfg.settings;
    };
in
{
    options.programs.nemo-trilium = {
        enable = lib.mkEnableOption "the Nemo menu entries that save files into Trilium";

        package = lib.mkOption {
            type = lib.types.package;
            default = self.packages.${pkgs.stdenv.hostPlatform.system}.nemo-trilium;
            defaultText = lib.literalMD "the `nemo-trilium` package from this flake";
            description = "The package providing the command and the two Nemo actions.";
        };

        settings = lib.mkOption {
            type = lib.types.attrsOf (
                lib.types.oneOf [
                    lib.types.str
                    lib.types.bool
                    lib.types.int
                ]
            );
            default = { };
            example = {
                url = "https://trilium.example.com";
                token_command = "cat /run/secrets/trilium_etapi_token";
                inbox = "#inbox";
            };
            description = ''
                The `[trilium]` section of `~/.config/nemo-trilium/config.ini`. Leave this empty to
                write the file by hand instead. Set `token_command` rather than `token`: anything
                given here is written to the world-readable Nix store.
            '';
        };
    };

    config = lib.mkIf cfg.enable {
        warnings = lib.optional (cfg.settings ? token && cfg.settings.token != "") ''
            programs.nemo-trilium.settings.token puts the ETAPI token in the world-readable Nix
            store. Use token_command to read it from a secret at runtime instead.
        '';

        # Nemo finds the actions under the package's share/nemo/actions through XDG_DATA_DIRS.
        home.packages = [ cfg.package ];

        xdg.configFile."nemo-trilium/config.ini" = lib.mkIf (cfg.settings != { }) {
            text = settingsFile;
        };
    };
}
