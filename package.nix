{
    lib,
    stdenvNoCC,
    python3,
    gtk3,
    gobject-introspection,
    wrapGAppsHook3,
    libnotify,
    xdg-utils,
}:

let
    python = python3.withPackages (ps: [
        ps.pygobject3
        ps.markdown
    ]);
in
stdenvNoCC.mkDerivation {
    pname = "nemo-trilium";
    version = "1.0.0";

    src = ./.;

    nativeBuildInputs = [
        wrapGAppsHook3
        gobject-introspection
    ];

    # GTK is reached through introspection rather than linked, so it has to be on GI_TYPELIB_PATH.
    buildInputs = [
        gtk3
        python
    ];

    dontBuild = true;

    # notify-send reports the outcome and xdg-open follows open_after_save.
    preFixup = ''
        gappsWrapperArgs+=(
            --prefix PATH : ${
                lib.makeBinPath [
                    libnotify
                    xdg-utils
                ]
            }
        )
    '';

    doCheck = true;

    checkPhase = ''
        runHook preCheck
        ${python}/bin/python -m compileall -q nemo_trilium nemo-trilium
        runHook postCheck
    '';

    installPhase = ''
        runHook preInstall

        mkdir -p $out/share/nemo-trilium
        cp -r nemo_trilium $out/share/nemo-trilium/

        install -Dm755 nemo-trilium $out/bin/nemo-trilium
        substituteInPlace $out/bin/nemo-trilium \
            --replace-fail 'os.path.dirname(os.path.abspath(__file__))' "'$out/share/nemo-trilium'"

        # Nemo spawns Exec with its own PATH, so the action points at the store path rather than a name.
        for action in actions/*.nemo_action; do
            target=$out/share/nemo/actions/$(basename "$action")
            install -Dm644 "$action" "$target"
            substituteInPlace "$target" --replace-fail '@bin@' "$out/bin/nemo-trilium"
        done

        runHook postInstall
    '';

    meta = {
        description = "Save files from Nemo's right-click menu into Trilium";
        longDescription = ''
            Two entries in Nemo's context menu. "Save to Trilium" uploads the selection to a
            configured inbox note without asking anything; "Save to Trilium as..." opens a window
            to search for the note to save under, name the note and pick what kind it should be.
            Text, Markdown and source files become editable notes, images become image notes and
            everything else is attached verbatim.
        '';
        homepage = "https://github.com/BeatLink/nemo-trilium";
        license = lib.licenses.gpl3Plus;
        platforms = lib.platforms.linux;
        mainProgram = "nemo-trilium";
    };
}
