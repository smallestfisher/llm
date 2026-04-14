from __future__ import annotations

from pathlib import Path

# Compatibility shim so legacy `app.*` imports resolve to `backend/app` when
# the rewrite backend is started from the repository root.
_BACKEND_APP_DIR = Path(__file__).resolve().parent.parent / "backend" / "app"
__path__ = [str(_BACKEND_APP_DIR)]
