from __future__ import annotations

import json
import platform
import subprocess


def notify(title: str, message: str) -> None:
    """Show a best-effort macOS notification without evaluating shell text."""
    if platform.system() != "Darwin":
        return
    script = "display notification " + json.dumps(message[:220]) + " with title " + json.dumps(title[:80])
    try:
        subprocess.Popen(
            ["/usr/bin/osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass
