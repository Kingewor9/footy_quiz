"""Vercel entrypoint. Vercel serves the `app` object as a serverless function."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.routes import app  # noqa: E402,F401
