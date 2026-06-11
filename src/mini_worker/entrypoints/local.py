"""Public `youagent` console entrypoint.

The implementation currently lives in `mini_worker.local_cli` for backwards compatibility.
New code should prefer importing this entrypoint module.
"""

from ..local_cli import main


__all__ = ["main"]
