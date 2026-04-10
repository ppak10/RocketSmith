from .__main__ import app
from .version import register_cadsmith_version
from .extract import register_cadsmith_extract
from .visualize import register_cadsmith_visualize

__all__ = ["app"]

_ = register_cadsmith_version(app)
_ = register_cadsmith_extract(app)
_ = register_cadsmith_visualize(app)
