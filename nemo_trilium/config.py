"""Reads the settings file, and runs the command that hands over the ETAPI token."""

import configparser
import os
import shlex
import subprocess

SECTION = "trilium"

DEFAULTS = {
    "url": "http://localhost:8080",
    "token": "",
    "token_command": "",
    "inbox": "root",
    "open_after_save": "false",
    "verify_tls": "true",
    "timeout": "30",
    "max_text_size": "2097152",
}

SAMPLE = """\
[trilium]
# The address of the Trilium server, as you would type it into a browser.
url = http://localhost:8080

# The ETAPI token, made once by hand under Options > ETAPI in Trilium.
# Either paste it here and chmod 600 this file, or leave it empty and let
# token_command print it, which keeps the token out of this file entirely.
token =
# token_command = cat /run/secrets/trilium_etapi_token

# Where "Save to Trilium" drops things. A note ID, a search such as #inbox,
# or the title of a note.
inbox = root

# Open the new note in a browser once it has been saved.
open_after_save = false

# Set to false for a server behind a self-signed certificate.
verify_tls = true

# Seconds to wait on the server.
timeout = 30

# Files larger than this stay attachments even when their text could be a note.
max_text_size = 2097152
"""


class ConfigError(Exception):
    """A setting is missing or wrong in a way only the user can put right."""


def config_dir():
    """The directory holding the settings file."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "nemo-trilium")


def config_path():
    """The settings file itself."""
    return os.path.join(config_dir(), "config.ini")


def write_sample(path=None):
    """Drops a commented settings file in place, and says where it went."""
    path = path or config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(SAMPLE)
    os.chmod(path, 0o600)
    return path


class Config:
    """The settings, with the token fetched from whichever source is configured."""

    def __init__(self, path=None):
        self.path = path or config_path()
        self.existed = os.path.exists(self.path)
        parser = configparser.ConfigParser()
        parser.read_dict({SECTION: DEFAULTS})
        if self.existed:
            parser.read(self.path, encoding="utf-8")
        section = parser[SECTION]
        self.url = section.get("url", "").strip().rstrip("/")
        self.inbox = section.get("inbox", "").strip() or "root"
        self.open_after_save = section.getboolean("open_after_save", fallback=False)
        self.verify_tls = section.getboolean("verify_tls", fallback=True)
        self.timeout = section.getfloat("timeout", fallback=30.0)
        self.max_text_size = section.getint("max_text_size", fallback=2097152)
        self._token = section.get("token", "").strip()
        self._token_command = section.get("token_command", "").strip()

    @property
    def token(self):
        """The ETAPI token, run out of token_command when one is set."""
        if self._token_command:
            return self._read_token_command()
        return self._token

    def _read_token_command(self):
        """Runs token_command and takes its first line of output as the token."""
        try:
            output = subprocess.run(
                shlex.split(self._token_command),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            ).stdout
        except OSError as error:
            raise ConfigError(f"token_command could not be run: {error}") from error
        except subprocess.TimeoutExpired as error:
            raise ConfigError("token_command took too long to answer") from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or f"exit status {error.returncode}"
            raise ConfigError(f"token_command failed: {detail}") from error
        token = output.strip().splitlines()
        if not token or not token[0].strip():
            raise ConfigError("token_command printed nothing")
        return token[0].strip()

    def check(self):
        """Raises when the settings are not yet usable, saying what to fix."""
        if not self.existed:
            written = write_sample(self.path)
            raise ConfigError(f"No settings yet. A starting file is now at {written}; fill in the URL and token.")
        if not self.url:
            raise ConfigError(f"No url set in {self.path}")
        if not self.token:
            raise ConfigError(f"No token or token_command set in {self.path}")
