# Tests

This directory contains unit and integration tests for DBManager.

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_checksum.py

# Run with coverage
python -m pytest --cov=core --cov=api tests/
```

## Test Structure

- `test_checksum.py` - Checksum/verification tests
- (Add more tests as needed)

## Requirements

```bash
pip install pytest pytest-cov
```
