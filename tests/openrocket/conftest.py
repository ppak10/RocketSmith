import pytest

from unittest.mock import patch
from rocketsmith.openrocket.utils import get_openrocket_path


@pytest.fixture(scope="session")
def openrocket_jar():
    """
    Resolve the OpenRocket JAR path, skipping the test if not installed.
    Used by tests that require OpenRocket to actually be present.
    """
    try:
        return get_openrocket_path()
    except FileNotFoundError:
        pytest.skip("OpenRocket not installed — skipping integration test.")


@pytest.fixture(scope="session", autouse=True)
def _suppress_jvm_shutdown():
    """Prevent JPype from shutting down the JVM between test functions.

    The JVM can only be started once per process. This fixture patches
    jpype.shutdownJVM to a no-op so that all integration tests share a
    single JVM session started on first use.
    """
    with patch("jpype.shutdownJVM", lambda: None):
        yield
