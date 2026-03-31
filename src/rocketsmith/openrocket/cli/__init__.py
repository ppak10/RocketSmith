from .__main__ import app
from .install import register_openrocket_install
from .simulation import register_openrocket_run_simulation
from .version import register_openrocket_version
from .inspect import register_openrocket_inspect
from .new import register_openrocket_new
from .create_component import register_openrocket_create_component
from .read_component import register_openrocket_read_component
from .update_component import register_openrocket_update_component
from .delete_component import register_openrocket_delete_component

_ = register_openrocket_install(app)
_ = register_openrocket_run_simulation(app)
_ = register_openrocket_version(app)
_ = register_openrocket_inspect(app)
_ = register_openrocket_new(app)
_ = register_openrocket_create_component(app)
_ = register_openrocket_read_component(app)
_ = register_openrocket_update_component(app)
_ = register_openrocket_delete_component(app)

__all__ = ["app"]
