"""App package init.

Loads variables from a project-root ``.env`` file into the environment before
any submodule reads ``os.getenv(...)``. Real environment variables always win
over ``.env`` values, and a missing ``.env`` is a no-op.
"""

from pathlib import Path

from dotenv import load_dotenv

# app/__init__.py -> app/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
