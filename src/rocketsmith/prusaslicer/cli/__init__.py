from .__main__ import app
from .install import register_prusaslicer_install
from .version import register_prusaslicer_version

_ = register_prusaslicer_install(app)
_ = register_prusaslicer_version(app)

__all__ = ["app"]
