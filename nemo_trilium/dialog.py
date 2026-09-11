"""The window that asks where in Trilium the selection should be saved."""

import os
import threading

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk, Pango

from .etapi import EtapiError
from .send import resolve_parent, send_all

SEARCH_DELAY = 300

KIND_CHOICES = (
    ("auto", "Whatever suits the file"),
    ("text", "Text note"),
    ("code", "Code note"),
    ("file", "Attachment"),
    ("image", "Image"),
)


class NoteRow(Gtk.ListBoxRow):
    """One note offered as a destination, showing its title above the trail to it."""

    def __init__(self, note_id, title, path):
        super().__init__()
        self.note_id = note_id
        self.note_title = title
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        name = Gtk.Label(label=title, xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        box.add(name)
        if path:
            trail = Gtk.Label(label=path, xalign=0)
            trail.set_ellipsize(Pango.EllipsizeMode.START)
            trail.get_style_context().add_class("dim-label")
            trail.set_attributes(_smaller())
            box.add(trail)
        self.add(box)


def _smaller():
    """Pango attributes that make the trail under a title a little quieter."""
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_scale_new(0.85))
    return attributes


class SaveDialog(Gtk.Dialog):
    """Asks for a title, a destination and a note kind, then does the upload itself."""

    def __init__(self, api, config, paths):
        super().__init__(title="Save to Trilium", modal=True)
        self.api = api
        self.config = config
        self.paths = paths
        self.results = None
        self.destination = ""
        self._search_timer = 0
        self._search_serial = 0
        self._build()
        self._load_inbox()

    # ===== Layout =======================================================================================================

    def _build(self):
        """Lays the window out."""
        self.set_default_size(480, 540)
        self.set_border_width(0)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.save_button = self.add_button("Save", Gtk.ResponseType.OK)
        self.save_button.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(12)
        # The content area packs with add(), which does not expand, so the note list would collapse.
        self.get_content_area().pack_start(box, True, True, 0)

        box.add(self._title_widget())
        box.add(_heading("Save in"))

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search your notes")
        self.search.set_activates_default(True)
        self.search.connect("search-changed", self._on_search_changed)
        box.add(self.search)

        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.connect("row-activated", lambda *_: self.response(Gtk.ResponseType.OK))
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_min_content_height(220)
        scroller.add(self.list)
        box.pack_start(scroller, True, True, 0)

        box.add(_heading("Save as"))
        self.kind = Gtk.ComboBoxText()
        for value, label in KIND_CHOICES:
            self.kind.append(value, label)
        self.kind.set_active_id("auto")
        box.add(self.kind)

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        status.add(self.spinner)
        self.status = Gtk.Label(xalign=0)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.get_style_context().add_class("dim-label")
        status.pack_start(self.status, True, True, 0)
        box.add(status)

    def _title_widget(self):
        """The title entry for a single file, or a note of how many are going at once."""
        if len(self.paths) == 1:
            frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            frame.add(_heading("Title"))
            self.title = Gtk.Entry()
            self.title.set_text(os.path.basename(self.paths[0]))
            self.title.set_activates_default(True)
            frame.add(self.title)
            return frame
        self.title = None
        label = Gtk.Label(xalign=0)
        label.set_text(f"{len(self.paths)} files, each saved under its own name.")
        label.get_style_context().add_class("dim-label")
        return label

    # ===== Destinations =================================================================================================

    def _load_inbox(self):
        """Fills the list with the configured inbox and the tree root to start from."""
        self._set_busy(True, "Looking up your inbox")
        threading.Thread(target=self._load_inbox_worker, daemon=True).start()

    def _load_inbox_worker(self):
        """Resolves the configured inbox off the main thread."""
        rows = []
        message = ""
        try:
            note_id = resolve_parent(self.api, self.config.inbox)
            note = self.api.get_note(note_id) or {}
            rows.append((note_id, note.get("title") or note_id, self.api.path_of(note)))
        except EtapiError as error:
            message = str(error)
        if not any(note_id == "root" for note_id, _, _ in rows):
            rows.append(("root", "Note tree root", ""))
        GLib.idle_add(self._show_rows, rows, None, message)

    def _on_search_changed(self, entry):
        """Waits a moment after typing stops before asking the server."""
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        self._search_timer = GLib.timeout_add(SEARCH_DELAY, self._start_search, entry.get_text().strip())

    def _start_search(self, query):
        """Kicks off one search, or goes back to the inbox when the box is emptied."""
        self._search_timer = 0
        if not query:
            self._load_inbox()
            return False
        self._search_serial += 1
        self._set_busy(True, "Searching")
        threading.Thread(target=self._search_worker, args=(query, self._search_serial), daemon=True).start()
        return False

    def _search_worker(self, query, serial):
        """Runs a search off the main thread and hands the rows back."""
        try:
            notes = self.api.search(query)
            rows = [(note["noteId"], note.get("title") or note["noteId"], self.api.path_of(note)) for note in notes]
            GLib.idle_add(self._show_rows, rows, serial, "")
        except EtapiError as error:
            GLib.idle_add(self._show_rows, [], serial, str(error))

    def _show_rows(self, rows, serial, message=""):
        """Replaces the list, ignoring answers to searches that have been typed past."""
        if serial is not None and serial != self._search_serial:
            return False
        for child in self.list.get_children():
            self.list.remove(child)
        for note_id, title, path in rows:
            self.list.add(NoteRow(note_id, title, path))
        self.list.show_all()
        first = self.list.get_row_at_index(0)
        if first:
            self.list.select_row(first)
        self._set_busy(False, message or ("" if rows else "Nothing matched"))
        return False

    # ===== Saving =======================================================================================================

    def _on_response(self, _dialog, response):
        """Starts the upload on Save, and closes on anything else."""
        if response != Gtk.ResponseType.OK:
            self._finish(None)
            return
        row = self.list.get_selected_row()
        if row is None:
            self._set_busy(False, "Pick a note to save under")
            return
        title = self.title.get_text().strip() if self.title else None
        self._set_busy(True, f"Saving to {row.note_title}")
        self.set_response_sensitive(Gtk.ResponseType.OK, False)
        self.search.set_sensitive(False)
        threading.Thread(
            target=self._save_worker,
            args=(row.note_id, row.note_title, title, self.kind.get_active_id()),
            daemon=True,
        ).start()

    def _save_worker(self, note_id, note_title, title, kind):
        """Uploads off the main thread, then closes the window."""
        results = send_all(self.api, self.paths, note_id, title, kind, self.config.max_text_size)
        GLib.idle_add(self._finish, results, note_title)

    def _finish(self, results, destination=""):
        """Remembers the outcome and leaves the main loop."""
        self.results = results
        self.destination = destination
        self.destroy()
        Gtk.main_quit()
        return False

    # ===== Feedback =====================================================================================================

    def _set_busy(self, busy, message=""):
        """Shows or hides the spinner and the line of status under it."""
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.spinner.set_visible(busy)
        self.status.set_text(message)
        return False


def _heading(text):
    """A small bold caption above a field."""
    label = Gtk.Label(xalign=0)
    label.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
    return label


def ask(api, config, paths):
    """Opens the picker and returns what was saved and where, or None when cancelled."""
    dialog = SaveDialog(api, config, paths)
    dialog.show_all()
    Gtk.main()
    return dialog.results, dialog.destination
