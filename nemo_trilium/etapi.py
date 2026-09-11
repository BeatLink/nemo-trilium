"""A small client for the part of Trilium's ETAPI this needs."""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


class EtapiError(Exception):
    """The server refused a request or could not be reached."""


class Etapi:
    """A Trilium server, addressed through its ETAPI with a fixed token."""

    def __init__(self, url, token, timeout=30.0, verify_tls=True):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._context = None if verify_tls else ssl._create_unverified_context()
        self._titles = {}

    # ===== Requests =====================================================================================================

    def _request(self, method, path, body=None, data=None, headers=None):
        """Sends one request and returns the decoded JSON, or None when there is no body."""
        payload = data
        request_headers = {"Authorization": self.token}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        request = urllib.request.Request(
            f"{self.url}/etapi{path}",
            data=payload,
            method=method,
            headers=request_headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self._context) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise EtapiError(self._describe(error)) from error
        except urllib.error.URLError as error:
            raise EtapiError(f"Cannot reach {self.url}: {error.reason}") from error
        except (TimeoutError, ssl.SSLError) as error:
            raise EtapiError(f"Cannot reach {self.url}: {error}") from error
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _describe(error):
        """Turns an HTTP failure into the sentence the user sees."""
        try:
            detail = json.loads(error.read()).get("message", "")
        except Exception:
            detail = ""
        if error.code == 401:
            return "Trilium rejected the ETAPI token"
        return f"Trilium answered {error.code}{': ' + detail if detail else ''}"

    # ===== Notes ========================================================================================================

    def app_info(self):
        """Asks the server what it is, which is the cheapest way to test the settings."""
        return self._request("GET", "/app-info")

    def get_note(self, note_id):
        """Reads one note's metadata."""
        return self._request("GET", f"/notes/{urllib.parse.quote(note_id)}")

    def search(self, query, limit=25):
        """Searches notes with Trilium's own search syntax."""
        params = urllib.parse.urlencode({"search": query, "limit": limit, "fastSearch": "false"})
        result = self._request("GET", f"/notes?{params}")
        return (result or {}).get("results", [])

    def create_note(self, parent_note_id, title, note_type, mime, content=""):
        """Creates a note under a parent and returns its ID."""
        result = self._request(
            "POST",
            "/create-note",
            body={
                "parentNoteId": parent_note_id,
                "title": title,
                "type": note_type,
                "mime": mime,
                "content": content,
            },
        )
        note_id = ((result or {}).get("note") or {}).get("noteId")
        if not note_id:
            raise EtapiError("Trilium created no note")
        return note_id

    def set_content(self, note_id, data, binary=False):
        """Replaces a note's content, sending raw bytes when it is not text."""
        headers = {"Content-Type": "application/octet-stream" if binary else "text/plain"}
        if binary:
            headers["Content-Transfer-Encoding"] = "binary"
        payload = data if isinstance(data, bytes) else data.encode("utf-8")
        self._request("PUT", f"/notes/{urllib.parse.quote(note_id)}/content", data=payload, headers=headers)

    def create_label(self, note_id, name, value=""):
        """Attaches a label to a note."""
        self._request(
            "POST",
            "/attributes",
            body={
                "noteId": note_id,
                "type": "label",
                "name": name,
                "value": value,
                "position": 10,
                "isInheritable": False,
            },
        )

    # ===== Paths ========================================================================================================

    def _cached_note(self, note_id):
        """A note's metadata, remembered so a page of search results costs few requests."""
        if note_id not in self._titles:
            try:
                self._titles[note_id] = self.get_note(note_id) or {}
            except EtapiError:
                self._titles[note_id] = {}
        return self._titles[note_id]

    def title_of(self, note_id):
        """The title of a note."""
        return self._cached_note(note_id).get("title") or note_id

    def path_of(self, note, depth=6):
        """Builds a readable trail of ancestor titles above a note."""
        parents = note.get("parentNoteIds") or []
        current = parents[0] if parents else None
        trail = []
        while current and current != "root" and len(trail) < depth:
            ancestor = self._cached_note(current)
            trail.append(ancestor.get("title") or current)
            parents = ancestor.get("parentNoteIds") or []
            current = parents[0] if parents else None
        return " / ".join(reversed(trail))

    def web_url(self, note_id):
        """The address that opens a note in a browser."""
        return f"{self.url}/#{note_id}"
