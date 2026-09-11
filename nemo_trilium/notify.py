"""Reports the outcome on the desktop, and falls back to standard error."""

import shutil
import subprocess
import sys

ICON = "trilium"


def notify(summary, body="", urgency="normal"):
    """Shows a desktop notification, printing instead when notify-send is missing."""
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "--app-name=Trilium", f"--icon={ICON}", f"--urgency={urgency}", summary, body],
            check=False,
        )
        return
    print(f"{summary}: {body}" if body else summary, file=sys.stderr)


def failure(summary, body=""):
    """Shows a failure the user needs to act on."""
    notify(summary, body, urgency="critical")
