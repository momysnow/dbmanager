import pytest
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

@pytest.fixture
def temp_home():
    """Fixture to create a temporary home directory for config storage"""
    with TemporaryDirectory() as temp_dir:
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_dir
        os.environ["DBMANAGER_DATA_DIR"] = str(Path(temp_dir) / ".dbmanager")
        
        yield Path(temp_dir)
        
        # Cleanup
        if old_home:
            os.environ["HOME"] = old_home
        if "DBMANAGER_DATA_DIR" in os.environ:
            del os.environ["DBMANAGER_DATA_DIR"]

@pytest.fixture
def mock_security():
    """Fixture to mock SecurityManager if needed"""
    from core.security import SecurityManager
    return SecurityManager
