import pytest

from rocketsmith.prusaslicer.utils import get_prusaslicer_path


@pytest.fixture(scope="session")
def prusaslicer_exe():
    """
    Resolve the PrusaSlicer executable path, skipping the test if not installed.
    Used by tests that require PrusaSlicer to actually be present.
    """
    try:
        return get_prusaslicer_path()
    except FileNotFoundError:
        pytest.skip("PrusaSlicer not installed — skipping integration test.")
