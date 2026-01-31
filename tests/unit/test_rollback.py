import pytest
from unittest.mock import MagicMock, patch
from core.manager import DBManager
from pathlib import Path

@pytest.fixture
def mock_verify_checksum():
    with patch("core.manager.verify_checksum", return_value=True) as mock:
        yield mock

def test_restore_creates_safety_snapshot(temp_home, mock_verify_checksum):
    """Test that restore_database triggers a safety snapshot"""
    manager = DBManager()
    
    # Mock everything
    manager.config_manager = MagicMock()
    manager.get_provider_instance = MagicMock()
    
    # Setup mocks
    provider = MagicMock()
    manager.get_provider_instance.return_value = provider
    manager.backup_database = MagicMock(return_value="/tmp/safety.dump")
    provider.restore.return_value = True
    
    # Mock file existence checks
    # We need side_effect to return True generally but handle specific cases if needed
    with patch("pathlib.Path.exists", return_value=True):
        manager.restore_database(1, "/tmp/backup.dump", create_safety_snapshot=True)
    
    # Verify backup was called with tag="safety_snapshot"
    manager.backup_database.assert_called_with(1, tag="safety_snapshot")
    
    # Verify restore was called
    provider.restore.assert_called_with("/tmp/backup.dump", progress=None)

def test_rollback_on_failure(temp_home, mock_verify_checksum):
    """Test that rollback occurs if restore fails"""
    manager = DBManager()
    
    # Mock
    manager.config_manager = MagicMock()
    manager.get_provider_instance = MagicMock()
    
    provider = MagicMock()
    manager.get_provider_instance.return_value = provider
    manager.backup_database = MagicMock(return_value="/tmp/safety.dump")
    
    # Simulate Restore Failure then Success (for rollback)
    provider.restore.side_effect = [RuntimeError("Restore BOOM"), True]
    
    # Mock os.path.exists to simulate safety snapshot existing
    with patch("os.path.exists", return_value=True), \
         patch("pathlib.Path.exists", return_value=True):
         
         # Should verify exception bubbles up, but msg contains "ROLLBACK SUCCESSFUL"
         with pytest.raises(RuntimeError) as excinfo:
             manager.restore_database(1, "/tmp/backup.dump", create_safety_snapshot=True)
         
         assert "ROLLBACK SUCCESSFUL" in str(excinfo.value)
    
    # Verify restore called twice: once for target, once for rollback
    assert provider.restore.call_count == 2
    # Second call should be the safety snapshot
    assert provider.restore.call_args_list[1][0][0] == "/tmp/safety.dump"
