import pytest

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
