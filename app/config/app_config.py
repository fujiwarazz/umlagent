
from pathlib import Path
import threading
import tomli as tomllib

from pathlib import Path
from typing import Dict

from pydantic import BaseModel, Field
def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

