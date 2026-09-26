"""Vercel serverless entrypoint — exposes the FastAPI app.

Vercel installs api/requirements.txt (slim) for this function instead of the
root requirements.txt, which bundles to ~6.3 GB and exceeds the 500 MB limit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.routes import app  # noqa: E402,F401
