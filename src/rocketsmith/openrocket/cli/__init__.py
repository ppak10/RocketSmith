from .__main__ import app
from .install import register_openrocket_install
from .version import register_openrocket_version

_ = register_openrocket_install(app)
_ = register_openrocket_version(app)

__all__ = ["app"]
