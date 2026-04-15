"""Constants for STEP ASCII rendering."""

import numpy as np

# ASCII shading gradient: index 0 = darkest, last index = brightest
SHADE_CHARS = " .,:;i1tfLCG08@#"

# Light direction (normalized), from top-right-front
_LIGHT = np.array([1.0, 2.0, 1.5])
LIGHT_DIR: np.ndarray = _LIGHT / np.linalg.norm(_LIGHT)

# View direction for isometric: camera is at (1,1,1) looking toward origin
_VIEW = np.array([1.0, 1.0, 1.0])
VIEW_DIR: np.ndarray = _VIEW / np.linalg.norm(_VIEW)

# Terminal character aspect ratio (width / height)
# Typical terminals: chars are roughly 2× taller than wide
CHAR_ASPECT: float = 0.5
