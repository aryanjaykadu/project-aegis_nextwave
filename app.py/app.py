from pathlib import Path
import sys

project_dir = Path(__file__).resolve().parent / "project-aegis"
sys.path.insert(0, str(project_dir))

from backend.main import app
