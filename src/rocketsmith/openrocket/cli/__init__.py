from .__main__ import app
from .install import register_openrocket_install
from .simulation import register_openrocket_run_flight
from .version import register_openrocket_version
from .inspect import register_openrocket_inspect
from .new import register_openrocket_new
from .create_component import register_openrocket_create_component
from .read_component import register_openrocket_read_component
from .update_component import register_openrocket_update_component
from .delete_component import register_openrocket_delete_component
from .list_motors import register_openrocket_list_motors
from .list_presets import register_openrocket_list_presets
from .list_materials import register_openrocket_list_materials
from .database import register_openrocket_database

_ = register_openrocket_install(app)
_ = register_openrocket_run_flight(app)
_ = register_openrocket_version(app)
_ = register_openrocket_inspect(app)
_ = register_openrocket_new(app)
_ = register_openrocket_create_component(app)
_ = register_openrocket_read_component(app)
_ = register_openrocket_update_component(app)
_ = register_openrocket_delete_component(app)
_ = register_openrocket_list_motors(app)
_ = register_openrocket_list_presets(app)
_ = register_openrocket_list_materials(app)
_ = register_openrocket_database(app)

__all__ = ["app"]
