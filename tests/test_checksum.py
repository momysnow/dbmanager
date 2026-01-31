#!/usr/bin/env python3
"""Test script for backup checksum functionality"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.backup_utils import (
    calculate_checksum,
    save_checksum,
    verify_checksum,
    verify_backup
)

def test_checksum_workflow():
    """Test the complete checksum workflow"""
    print("🧪 Testing Backup Checksum Functionality\n")
    
    # Create a temporary test backup file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
        test_file = f.name
        f.write("-- Test backup file\n")
        f.write("CREATE TABLE test (id INT);\n")
        f.write("INSERT INTO test VALUES (1), (2), (3);\n")
    
    try:
        print(f"📄 Created test file: {Path(test_file).name}")
        
        # Test 1: Calculate checksum
        print("\n1️⃣  Testing checksum calculation...")
        checksum = calculate_checksum(test_file)
        print(f"   ✅ SHA256: {checksum[:16]}...")
        
        # Test 2: Save checksum file
        print("\n2️⃣  Testing checksum file creation...")
        checksum_file = save_checksum(test_file)
        print(f"   ✅ Checksum file created: {Path(checksum_file).name}")
        
        # Test 3: Verify checksum
        print("\n3️⃣  Testing checksum verification...")
        is_valid = verify_checksum(test_file)
        if is_valid:
            print(f"   ✅ Checksum VERIFIED")
        else:
            print(f"   ❌ Checksum FAILED")
            return False
        
        # Test 4: Comprehensive backup verification
        print("\n4️⃣  Testing comprehensive backup verification...")
        result = verify_backup(test_file)
        print(f"   Valid: {result['valid']}")
        print(f"   File exists: {result['file_exists']}")
        print(f"   File size: {result['file_size']} bytes")
        print(f"   Checksum valid: {result['checksum_valid']}")
        
        if result['valid']:
            print(f"   ✅ Comprehensive verification PASSED")
        else:
            print(f"   ❌ Verification FAILED:")
            for error in result['errors']:
                print(f"      • {error}")
            return False
        
        # Test 5: Corrupt file and verify detection
        print("\n5️⃣  Testing corruption detection...")
        with open(test_file, 'a') as f:
            f.write("\n-- CORRUPTED DATA --\n")
        
        is_valid = verify_checksum(test_file)
        if not is_valid:
            print(f"   ✅ Corruption detected successfully")
        else:
            print(f"   ❌ Failed to detect corruption")
            return False
        
        print("\n" + "="*50)
        print("🎉 All tests PASSED!")
        print("="*50)
        return True
        
    finally:
        # Cleanup
        Path(test_file).unlink(missing_ok=True)
        Path(f"{test_file}.sha256").unlink(missing_ok=True)

if __name__ == "__main__":
    success = test_checksum_workflow()
    sys.exit(0 if success else 1)
