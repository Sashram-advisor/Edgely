"""Load the vendored AI Tutor FastAPI app without modifying its source.

The AI Tutor project lives in ``services/ai_tutor`` with its original
``backend/app`` package layout.  Importing it as ``backend.app.main`` from the
merged process would collide with Edgely's own ``backend/`` directory, depending
on which directory uvicorn was started from.

Instead we load the package under a private name, ``edgely_ai_tutor``.  Every
module in the vendored app uses package-relative imports (``from .chat import
...``), so they continue to resolve inside that private package.  No file is
edited and no ``sys.path`` mutation is needed.

The function is cached because importing the app creates module-level state
(a FastAPI app and a Supabase client factory).  Mount it exactly once.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI

# backend/app/integrations/ai_tutor_mount.py -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_AI_TUTOR_APP = _REPO_ROOT / "services" / "ai_tutor" / "backend" / "app"
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_NAME = "edgely_ai_tutor"


@lru_cache(maxsize=1)
def get_ai_tutor_app() -> FastAPI:
    """Return the untouched AI Tutor FastAPI application."""
    
    # The tutor reads settings from ".env" in the current folder plus the file named by ENV_FILE.
    # Point ENV_FILE at backend/.env so both halves read the same file from any folder.
    os.environ.setdefault("ENV_FILE", str(_BACKEND_ROOT / ".env"))

    main_file = _AI_TUTOR_APP / "main.py"
    if not main_file.is_file():
        raise RuntimeError(f"AI Tutor sources are missing. Expected {main_file}.")

    package = sys.modules.get(_PACKAGE_NAME)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _PACKAGE_NAME,
            _AI_TUTOR_APP / "__init__.py",
            submodule_search_locations=[str(_AI_TUTOR_APP)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not create an import spec for {_AI_TUTOR_APP}.")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_PACKAGE_NAME] = package
        spec.loader.exec_module(package)

    # Imported lazily on purpose: config.py reads backend/.env and dependencies
    # (anthropic, supabase, ...) are only needed in merged mode.
    from importlib import import_module

    ai_tutor_main = import_module(f"{_PACKAGE_NAME}.main")
    ai_tutor_app: FastAPI = ai_tutor_main.app
    return ai_tutor_app
