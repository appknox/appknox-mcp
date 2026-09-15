"""Thin shim so `install.sh`/`uninstall.sh` can call the config-writer without
needing the package installed or its dependencies synced.

The actual logic lives in `src/appknox_mcp/configure.py` (imported here by
inserting `src/` onto `sys.path` directly, bypassing the normal package
import machinery) — that module is stdlib-only, so this still runs under
`uv run --no-project` with no dependency resolution. It's also part of the
installed package itself, so `appknox-mcp --configure`/`--remove-client`
(for anyone who installed from PyPI, with no repo checkout at all) call the
exact same code.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from appknox_mcp.configure import main

if __name__ == "__main__":
    sys.exit(main())
