"""Uploads files into Trilium and says what became of each one."""

import os
import shutil
import subprocess

from .etapi import EtapiError
from .notetype import prepare


class Result:
    """What happened to one file."""

    def __init__(self, path, note_id=None, title=None, note_type=None, error=None):
        self.path = path
        self.note_id = note_id
        self.title = title
        self.note_type = note_type
        self.error = error

    @property
    def ok(self):
        """Whether the file reached Trilium."""
        return self.error is None


# ===== Destination ======================================================================================================


def resolve_parent(api, spec):
    """Turns a note ID, a search or a title from the settings into a note ID."""
    spec = (spec or "root").strip()
    if spec in ("", "root"):
        return "root"
    if not spec.startswith(("#", "~", "=")):
        try:
            note = api.get_note(spec)
            if note and note.get("noteId"):
                return note["noteId"]
        except EtapiError:
            pass
    results = api.search(spec, limit=1)
    if not results:
        raise EtapiError(f"No note in Trilium matches {spec!r}")
    return results[0]["noteId"]


# ===== Upload ===========================================================================================================


def send_file(api, path, parent_note_id, title=None, kind="auto", max_text_size=2097152):
    """Saves one file into Trilium under a parent note and returns the result."""
    name = title or os.path.basename(path)
    try:
        prepared = prepare(path, kind=kind, max_text_size=max_text_size)
        text = "" if prepared.binary else prepared.content
        note_id = api.create_note(parent_note_id, name, prepared.note_type, prepared.mime, text)
        if prepared.binary:
            api.set_content(note_id, prepared.content, binary=True)
        if prepared.original_name:
            api.create_label(note_id, "originalFileName", prepared.original_name)
        return Result(path, note_id, name, prepared.note_type)
    except (EtapiError, OSError) as error:
        return Result(path, title=name, error=str(error))


def send_all(api, paths, parent_note_id, title=None, kind="auto", max_text_size=2097152):
    """Saves every file, using the given title only when there is a single one."""
    only = title if len(paths) == 1 else None
    return [send_file(api, path, parent_note_id, only, kind, max_text_size) for path in paths]


def open_notes(api, results):
    """Opens the saved notes in a browser."""
    if not shutil.which("xdg-open"):
        return
    for result in results:
        if result.ok:
            subprocess.Popen(
                ["xdg-open", api.web_url(result.note_id)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


# ===== Reporting ========================================================================================================


def summarise(results, destination):
    """Turns the results into the headline and body of one notification."""
    saved = [result for result in results if result.ok]
    failed = [result for result in results if not result.ok]
    if not failed:
        if len(saved) == 1:
            return f"Saved to {destination}", saved[0].title
        return f"Saved {len(saved)} files to {destination}", ", ".join(result.title for result in saved[:6])
    if not saved:
        if len(failed) == 1:
            return "Could not save to Trilium", f"{failed[0].title}: {failed[0].error}"
        return "Could not save to Trilium", failed[0].error
    lines = [f"{result.title}: {result.error}" for result in failed[:4]]
    return f"Saved {len(saved)} of {len(results)} files to {destination}", "\n".join(lines)
