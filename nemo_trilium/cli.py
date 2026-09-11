"""The command line that Nemo's actions call."""

import argparse
import os
import sys

from . import VERSION
from .config import Config, ConfigError, config_path
from .etapi import Etapi, EtapiError
from .notetype import KINDS
from .notify import failure, notify
from .send import open_notes, resolve_parent, send_all, summarise


def parse(argv):
    """Reads the arguments Nemo or the user supplied."""
    parser = argparse.ArgumentParser(prog="nemo-trilium", description="Save files into Trilium.")
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    send = commands.add_parser("send", help="save files into Trilium")
    send.add_argument("files", nargs="+", help="the files to save")
    send.add_argument("--ask", action="store_true", help="open a window to choose the destination")
    send.add_argument("--parent", help="note ID, search or title to save under, instead of the configured inbox")
    send.add_argument("--title", help="title for the note, when saving a single file")
    send.add_argument("--type", choices=KINDS, default="auto", dest="kind", help="what kind of note to make")

    commands.add_parser("check", help="test the settings against the server")
    commands.add_parser("config", help="print the path of the settings file")

    return parser.parse_args(argv)


# ===== Commands =========================================================================================================


def command_check(config):
    """Reports what the configured server says about itself."""
    api = Etapi(config.url, config.token, config.timeout, config.verify_tls)
    info = api.app_info() or {}
    print(f"Connected to {config.url}")
    print(f"  Trilium {info.get('appVersion', '?')}, database {info.get('dbVersion', '?')}")
    parent = resolve_parent(api, config.inbox)
    print(f"  Inbox {config.inbox!r} is note {parent} ({api.title_of(parent)})")
    return 0


def command_send(config, options):
    """Saves the files, either straight to the inbox or wherever the window says."""
    paths = [path for path in options.files if os.path.isfile(path)]
    if not paths:
        failure("Nothing to save", "Only files can be saved to Trilium.")
        return 1

    api = Etapi(config.url, config.token, config.timeout, config.verify_tls)

    if options.ask:
        from .dialog import ask

        results, destination = ask(api, config, paths)
        if results is None:
            return 0
    else:
        parent = resolve_parent(api, options.parent or config.inbox)
        destination = api.title_of(parent)
        results = send_all(api, paths, parent, options.title, options.kind, config.max_text_size)

    summary, body = summarise(results, destination)
    if all(result.ok for result in results):
        notify(summary, body)
        if config.open_after_save:
            open_notes(api, results)
        return 0
    failure(summary, body)
    return 1


# ===== Entry ============================================================================================================


def main(argv=None):
    """Runs one command and turns any failure into a notification."""
    options = parse(sys.argv[1:] if argv is None else argv)
    if options.command == "config":
        print(config_path())
        return 0
    try:
        config = Config()
        config.check()
        if options.command == "check":
            return command_check(config)
        return command_send(config, options)
    except ConfigError as error:
        failure("Trilium is not set up yet", str(error))
        return 1
    except EtapiError as error:
        failure("Trilium refused the request", str(error))
        return 1
    # Nemo gives the action no terminal, so an unexpected failure has to be shown somewhere.
    except Exception as error:
        failure("Saving to Trilium went wrong", f"{type(error).__name__}: {error}")
        return 1
