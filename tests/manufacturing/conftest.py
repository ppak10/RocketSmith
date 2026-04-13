import pytest

from unittest.mock import patch
from rocketsmith.openrocket.utils import get_openrocket_path


@pytest.fixture(scope="session")
def openrocket_jar():
    """Resolve the OpenRocket JAR, skipping the test if not installed."""
    try:
        return get_openrocket_path()
    except FileNotFoundError:
        pytest.skip("OpenRocket not installed — skipping integration test.")


@pytest.fixture(scope="session", autouse=True)
def _suppress_jvm_shutdown():
    """Prevent JPype from shutting down the JVM between test functions."""
    with patch("jpype.shutdownJVM", lambda: None):
        yield
