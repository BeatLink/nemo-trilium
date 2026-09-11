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

    actions = [
        "nemo-trilium@beatlink.nemo_action"
        "nemo-trilium-ask@beatlink.nemo_action"
    ];
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

        home.packages = [ cfg.package ];

        # Nemo reads its actions from ~/.local/share/nemo/actions, not from XDG_DATA_DIRS.
        xdg.dataFile = lib.listToAttrs (
            map (action: {
                name = "nemo/actions/${action}";
                value.source = "${cfg.package}/share/nemo/actions/${action}";
            }) actions
        );

        xdg.configFile."nemo-trilium/config.ini" = lib.mkIf (cfg.settings != { }) {
            text = settingsFile;
        };
    };
}
