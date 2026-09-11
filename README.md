# Nemo Trilium

Two entries in Nemo's right-click menu that put the selected files into
[Trilium](https://github.com/TriliumNext/Trilium).

| Menu entry | What it does |
| --- | --- |
| **Save to Trilium** | Uploads straight to the inbox note named in the settings, with no window. A notification says what landed where. |
| **Save to Trilium as…** | Opens a window: search for the note to save under, change the title, choose what kind of note to make. |

Both work on several files at once.

## What each file becomes

A file is turned into the kind of note that suits it, so text arrives editable rather than as
something to download again.

| File | Note |
| --- | --- |
| `.md`, `.markdown` | Text note, the Markdown rendered |
| `.txt`, `.html`, `.log`, `.rst`, `.org` | Text note |
| Source and config files — `.py`, `.nix`, `.sh`, `.json`, `.yaml`, and so on | Code note, syntax highlighted |
| Images | Image note |
| Anything else, and any text file over `max_text_size` | Attachment, byte for byte |

The window lets you override this per save, and `--type` does the same on the command line.
Attachments and images keep their filename in an `originalFileName` label, which is where Trilium
looks when you download them again.

## Settings

Settings live in `~/.config/nemo-trilium/config.ini`. The first run writes a commented starting
file there and tells you to fill it in.

```ini
[trilium]
url = https://trilium.example.com
token_command = cat /run/secrets/trilium_etapi_token
inbox = #inbox
open_after_save = false
verify_tls = true
timeout = 30
max_text_size = 2097152
```

| Key | Meaning |
| --- | --- |
| `url` | The server's address, as you would type it into a browser. |
| `token` | An ETAPI token, made once by hand under **Options > ETAPI** in Trilium. Chmod the file to 600 if you put it here. |
| `token_command` | Run instead of `token`, and its first line of output is used. This keeps the token out of the file. |
| `inbox` | Where **Save to Trilium** drops things: a note ID, a search such as `#inbox`, or a note's title. Defaults to `root`. |
| `open_after_save` | Open each new note in a browser once it has been saved. |
| `verify_tls` | Set to `false` for a server behind a self-signed certificate. |
| `max_text_size` | Text files larger than this are attached rather than turned into notes. |

Trilium has no way to hand out an ETAPI token declaratively, so that one step is always manual.

## Command line

The actions are thin wrappers around one command, which is usable on its own.

```
nemo-trilium send FILE...            # to the configured inbox
nemo-trilium send --ask FILE...      # with the destination window
nemo-trilium send --parent '#inbox' --title 'Receipt' --type file FILE
nemo-trilium check                   # test the settings against the server
nemo-trilium config                  # print the path of the settings file
```

## Installing

### With Nix

```nix
{
    inputs.nemo-trilium.url = "github:BeatLink/nemo-trilium";
}
```

The flake gives you `packages.default`, `overlays.default` and a Home Manager module:

```nix
{
    imports = [ inputs.nemo-trilium.homeManagerModules.default ];

    programs.nemo-trilium = {
        enable = true;
        settings = {
            url = "https://trilium.example.com";
            token_command = "cat /run/secrets/trilium_etapi_token";
            inbox = "#inbox";
        };
    };
}
```

`settings` writes `config.ini` for you. Leave it out to keep the file hand-written, and use
`token_command` rather than `token` so the token never reaches the Nix store.

### Without Nix

Needs Python 3, PyGObject with GTK 3, and optionally `python-markdown` for rendered Markdown and
`libnotify` for the notifications.

```sh
git clone https://github.com/BeatLink/nemo-trilium
cd nemo-trilium
mkdir -p ~/.local/bin ~/.local/share/nemo/actions
ln -s "$PWD/nemo-trilium" ~/.local/bin/nemo-trilium
for action in actions/*.nemo_action; do
    sed "s|@bin@|$HOME/.local/bin/nemo-trilium|" "$action" > ~/.local/share/nemo/actions/$(basename "$action")
done
nemo-trilium config
```

Nemo picks up new actions on its own; `nemo -q` and reopening it forces the issue.

## Licence

GPL-3.0-or-later.
