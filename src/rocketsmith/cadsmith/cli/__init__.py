from .__main__ import app
from .extract_part import register_cadsmith_extract_part
from .visualize import register_cadsmith_visualize

__all__ = ["app"]

_ = register_cadsmith_extract_part(app)
_ = register_cadsmith_visualize(app)
