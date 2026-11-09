"""Test bootstrap: no live database, Supabase or Ollama is required.

The merged app constructs SQLAlchemy engines and reads pydantic settings at
import time.  Dummy values keep those constructors happy; the tests only inspect
route registration and pure functions, so no connection is ever opened.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

# Edgely's package root is backend/, not the repository root.
sys.path.insert(0, str(ROOT / "backend"))
