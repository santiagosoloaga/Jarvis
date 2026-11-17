# Hace importables los módulos de la raíz (atajos.py, habitos.py, etc.) desde tests/.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
