import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_project_dir(tmp_path, monkeypatch):
    """Point ROCKETSMITH_PROJECT_DIR at the per-test tmp_path so that tool
    side-effects (component_tree.json, parts/, etc.) never land in the repo root."""
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(tmp_path))


@pytest.fixture(scope="session")
def temp_project_root():
    """Create a temporary project root for testing."""
    temp_path = Path(tempfile.mkdtemp())

    out_dir = temp_path / "out"
    out_dir.mkdir()

    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def isolated_workspace():
    """Create an isolated workspace for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)
