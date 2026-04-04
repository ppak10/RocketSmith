import pytest
from unittest.mock import patch
from wa import create_workspace


@pytest.fixture(autouse=True)
def setup_workspace(tmp_path):
    workspaces_dir = tmp_path / "workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    with patch("wa.utils.get_project_root", return_value=tmp_path):
        create_workspace("test_ws", workspaces_dir)
        yield
