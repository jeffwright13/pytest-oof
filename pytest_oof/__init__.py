from pathlib import Path

from from_root import from_root
from single_source import get_version

__version__ = get_version(__name__, Path(__file__).parent.parent / "setup.py")
_project_root = from_root()
