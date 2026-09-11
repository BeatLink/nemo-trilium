"""Decides which kind of Trilium note a file should become, and prepares its content."""

import html
import mimetypes
import os

KINDS = ("auto", "text", "code", "file", "image")

MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".mkdn"}
HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
PLAIN_SUFFIXES = {".txt", ".text", ".log", ".rst", ".org", ""}

CODE_SUFFIXES = {
    ".c": "text/x-csrc",
    ".conf": "text/x-ini",
    ".cpp": "text/x-c++src",
    ".cs": "text/x-csharp",
    ".css": "text/css",
    ".dart": "text/x-dart",
    ".diff": "text/x-diff",
    ".el": "text/x-common-lisp",
    ".go": "text/x-go",
    ".h": "text/x-csrc",
    ".hpp": "text/x-c++src",
    ".hs": "text/x-haskell",
    ".ini": "text/x-ini",
    ".java": "text/x-java",
    ".js": "application/javascript",
    ".json": "application/json",
    ".kt": "text/x-kotlin",
    ".lua": "text/x-lua",
    ".mjs": "application/javascript",
    ".nix": "text/x-nix",
    ".patch": "text/x-diff",
    ".php": "application/x-httpd-php",
    ".pl": "text/x-perl",
    ".py": "text/x-python",
    ".r": "text/x-rsrc",
    ".rb": "text/x-ruby",
    ".rs": "text/x-rustsrc",
    ".scss": "text/x-scss",
    ".sh": "text/x-sh",
    ".sql": "text/x-sql",
    ".swift": "text/x-swift",
    ".tex": "text/x-stex",
    ".toml": "text/x-toml",
    ".ts": "application/typescript",
    ".vim": "text/x-vim",
    ".xml": "text/xml",
    ".yaml": "text/x-yaml",
    ".yml": "text/x-yaml",
    ".bash": "text/x-sh",
    ".zsh": "text/x-sh",
    ".csv": "text/csv",
}


class Prepared:
    """One file worked out into everything create-note and the content upload need."""

    def __init__(self, note_type, mime, content, binary, original_name=None):
        self.note_type = note_type
        self.mime = mime
        self.content = content
        self.binary = binary
        self.original_name = original_name


# ===== Conversions ======================================================================================================


def markdown_to_html(text):
    """Renders Markdown as the HTML a Trilium text note stores, falling back to plain text."""
    try:
        import markdown
    except ImportError:
        return plain_to_html(text)
    return markdown.markdown(text, extensions=["extra", "sane_lists", "nl2br"])


def plain_to_html(text):
    """Wraps plain text so a text note keeps its line breaks."""
    return "<pre>" + html.escape(text) + "</pre>"


def read_text(path):
    """Reads a file as text, or returns None when it is not text at all."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (UnicodeDecodeError, OSError):
        return None


# ===== Classification ===================================================================================================


def guess_mime(path):
    """The best guess at a file's media type."""
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def as_file(path, mime=None):
    """Prepares a file to be stored verbatim as an attachment note."""
    with open(path, "rb") as handle:
        data = handle.read()
    return Prepared("file", mime or guess_mime(path), data, True, os.path.basename(path))


def as_image(path, mime=None):
    """Prepares a file to be stored as an image note."""
    with open(path, "rb") as handle:
        data = handle.read()
    return Prepared("image", mime or guess_mime(path), data, True, os.path.basename(path))


def prepare(path, kind="auto", max_text_size=2097152):
    """Works out what a file should become in Trilium and reads it accordingly."""
    suffix = os.path.splitext(path)[1].lower()
    mime = guess_mime(path)
    too_big = os.path.getsize(path) > max_text_size

    if kind == "file":
        return as_file(path, mime)
    if kind == "image":
        return as_image(path, mime)

    if kind == "auto" and mime.startswith("image/"):
        return as_image(path, mime)
    if kind == "auto" and too_big:
        return as_file(path, mime)

    text = read_text(path)
    if text is None:
        return as_file(path, mime)

    if kind == "code":
        return Prepared("code", CODE_SUFFIXES.get(suffix, "text/plain"), text, False)
    if kind == "text":
        return Prepared("text", "text/html", _to_html(suffix, text), False)

    if suffix in CODE_SUFFIXES:
        return Prepared("code", CODE_SUFFIXES[suffix], text, False)
    if suffix in MARKDOWN_SUFFIXES or suffix in HTML_SUFFIXES or suffix in PLAIN_SUFFIXES:
        return Prepared("text", "text/html", _to_html(suffix, text), False)
    if mime.startswith("text/"):
        return Prepared("code", "text/plain", text, False)
    return as_file(path, mime)


def _to_html(suffix, text):
    """Turns a text file's contents into the HTML a text note holds."""
    if suffix in MARKDOWN_SUFFIXES:
        return markdown_to_html(text)
    if suffix in HTML_SUFFIXES:
        return text
    return plain_to_html(text)
