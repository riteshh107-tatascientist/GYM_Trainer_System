import math
from pathlib import Path
import ast

APP = Path(__file__).parents[1] / "app.py"

def test_app_is_valid_python():
    ast.parse(APP.read_text(encoding="utf-8"))

def test_angle_formula():
    # 90 degrees: (1,0), (0,0), (0,1)
    a=(1,0); b=(0,0); c=(0,1)
    import numpy as np
    ba=np.array(a)-np.array(b)
    bc=np.array(c)-np.array(b)
    value=np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc))
    assert abs(math.degrees(math.acos(value))) < 1e-6
