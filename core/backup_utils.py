"""Backup utility functions for checksum verification and integrity checks."""

import hashlib
from pathlib import Path
from typing import Optional


def calculate_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate checksum of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, md5, sha1)
    
    Returns:
        Hexadecimal hash string
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If unsupported algorithm
    """
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Select hash algorithm
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    # Read file in chunks to handle large files
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def save_checksum(backup_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate and save checksum file alongside backup.
    
    Args:
        backup_path: Path to the backup file
        algorithm: Hash algorithm to use
    
    Returns:
        Path to the generated checksum file
    
    Raises:
        FileNotFoundError: If backup file doesn't exist
    """
    checksum = calculate_checksum(backup_path, algorithm)
    
    # Create checksum file with algorithm extension
    checksum_file = f"{backup_path}.{algorithm}"
    
    # Write checksum in format: <hash> <filename>
    backup_filename = Path(backup_path).name
    with open(checksum_file, 'w') as f:
        f.write(f"{checksum}  {backup_filename}\n")
    
    return checksum_file


def verify_checksum(file_path: str, expected_hash: Optional[str] = None, 
                   algorithm: str = "sha256") -> bool:
    """
    Verify file integrity against checksum.
    
    Args:
        file_path: Path to the file to verify
        expected_hash: Expected hash (if None, reads from .sha256 file)
        algorithm: Hash algorithm to use
    
    Returns:
        True if checksum matches, False otherwise
    
    Raises:
        FileNotFoundError: If file or checksum file doesn't exist
    """
    # Calculate current hash
    current_hash = calculate_checksum(file_path, algorithm)
    
    # If no expected hash provided, try to read from checksum file
    if expected_hash is None:
        checksum_file = f"{file_path}.{algorithm}"
        if not Path(checksum_file).exists():
            raise FileNotFoundError(f"Checksum file not found: {checksum_file}")
        
        with open(checksum_file, 'r') as f:
            line = f.read().strip()
            # Parse format: <hash> <filename>
            expected_hash = line.split()[0]
    
    return current_hash == expected_hash


def verify_backup(backup_path: str) -> dict:
    """
    Comprehensive backup verification.
    
    Checks:
    - File exists and not empty
    - File size is reasonable
    - Checksum verification (if available)
    
    Args:
        backup_path: Path to backup file
    
    Returns:
        Dictionary with verification results:
        {
            'valid': bool,
            'file_exists': bool,
            'file_size': int,
            'checksum_valid': bool or None,
            'errors': list of error messages
        }
    """
    result = {
        'valid': True,
        'file_exists': False,
        'file_size': 0,
        'checksum_valid': None,
        'errors': []
    }
    
    backup_file = Path(backup_path)
    
    # Check file exists
    if not backup_file.exists():
        result['valid'] = False
        result['errors'].append(f"Backup file not found: {backup_path}")
        return result
    
    result['file_exists'] = True
    
    # Check file size
    file_size = backup_file.stat().st_size
    result['file_size'] = file_size
    
    if file_size == 0:
        result['valid'] = False
        result['errors'].append("Backup file is empty")
    
    # Check checksum if available
    checksum_file = Path(f"{backup_path}.sha256")
    if checksum_file.exists():
        try:
            checksum_valid = verify_checksum(backup_path)
            result['checksum_valid'] = checksum_valid
            if not checksum_valid:
                result['valid'] = False
                result['errors'].append("Checksum verification failed")
        except Exception as e:
            result['errors'].append(f"Checksum verification error: {e}")
            result['checksum_valid'] = False
            result['valid'] = False
    
    return result
