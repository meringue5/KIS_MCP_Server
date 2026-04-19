"""Compatibility entrypoint for existing MCP desktop configurations.

The application implementation lives in ``src/kis_mcp_server/app.py``.
Keep this file thin so existing commands that execute ``server.py`` from
the repository root continue to work during the migration to a package layout.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kis_mcp_server.app import main, mcp  # noqa: E402,F401


if __name__ == "__main__":
    main()
