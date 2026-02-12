"""Compression utilities for backup files.

Supports multiple compression algorithms:
- gzip (builtin, good compression, moderate speed)
- zstd (Facebook's Zstandard, excellent compression + speed)
- lz4 (very fast compression/decompression, moderate compression)
"""

import gzip
import os
from pathlib import Path
from typing import Optional

# Optional compression libraries
try:
    import zstandard as zstd

    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

try:
    import lz4.frame

    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False


class CompressionError(Exception):
    """Raised when compression/decompression fails"""

    pass


def get_available_algorithms() -> list:
    """
    Get list of available compression algorithms.

    Returns:
        List of algorithm names that are available
    """
    algorithms = ["gzip"]  # gzip is always available (builtin)

    if ZSTD_AVAILABLE:
        algorithms.append("zstd")

    if LZ4_AVAILABLE:
        algorithms.append("lz4")

    return algorithms


def compress_file(
    file_path: str,
    algorithm: str = "gzip",
    level: int = 6,
    remove_original: bool = False,
) -> str:
    """
    Compress a file using the specified algorithm.

    Args:
        file_path: Path to file to compress
        algorithm: Compression algorithm ('gzip', 'zstd', 'lz4')
        level: Compression level (1-9 for gzip, 1-22 for zstd, 1-12 for lz4)
        remove_original: Whether to delete original file after compression

    Returns:
        Path to compressed file

    Raises:
        CompressionError: If compression fails
        ValueError: If algorithm is not supported
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    algorithm = algorithm.lower()

    if algorithm == "gzip":
        compressed_path = f"{file_path}.gz"
        try:
            with open(file_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb", compresslevel=level) as f_out:
                    f_out.write(f_in.read())
        except Exception as e:
            raise CompressionError(f"gzip compression failed: {e}")

    elif algorithm == "zstd":
        if not ZSTD_AVAILABLE:
            raise ValueError(
                "zstd compression not available. Install: pip install zstandard"
            )

        compressed_path = f"{file_path}.zst"
        try:
            with open(file_path, "rb") as f_in:
                data = f_in.read()
                cctx = zstd.ZstdCompressor(level=level)
                compressed = cctx.compress(data)
                with open(compressed_path, "wb") as f_out:
                    f_out.write(compressed)
        except Exception as e:
            raise CompressionError(f"zstd compression failed: {e}")

    elif algorithm == "lz4":
        if not LZ4_AVAILABLE:
            raise ValueError("lz4 compression not available. Install: pip install lz4")

        compressed_path = f"{file_path}.lz4"
        try:
            with open(file_path, "rb") as f_in:
                data = f_in.read()
                compressed = lz4.frame.compress(data, compression_level=level)
                with open(compressed_path, "wb") as f_out:
                    f_out.write(compressed)
        except Exception as e:
            raise CompressionError(f"lz4 compression failed: {e}")

    else:
        raise ValueError(f"Unsupported compression algorithm: {algorithm}")

    # Remove original if requested
    if remove_original and os.path.exists(compressed_path):
        os.remove(file_path)

    return compressed_path


def decompress_file(
    file_path: str, output_path: Optional[str] = None, remove_compressed: bool = False
) -> str:
    """
    Decompress a file. Auto-detects algorithm from extension.

    Args:
        file_path: Path to compressed file (.gz, .zst, .lz4)
        output_path: Optional output path (auto-generated if None)
        remove_compressed: Whether to delete compressed file after decompression

    Returns:
        Path to decompressed file

    Raises:
        CompressionError: If decompression fails
        ValueError: If file extension is not recognized
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Auto-detect algorithm from extension
    file_path_obj = Path(file_path)
    extension = file_path_obj.suffix.lower()

    # Determine output path
    if output_path is None:
        output_path = str(file_path_obj.with_suffix(""))

    if extension == ".gz":
        try:
            with gzip.open(file_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    f_out.write(f_in.read())
        except Exception as e:
            raise CompressionError(f"gzip decompression failed: {e}")

    elif extension == ".zst":
        if not ZSTD_AVAILABLE:
            raise ValueError(
                "zstd decompression not available. Install: pip install zstandard"
            )

        try:
            with open(file_path, "rb") as f_in:
                compressed = f_in.read()
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(compressed)
                with open(output_path, "wb") as f_out:
                    f_out.write(decompressed)
        except Exception as e:
            raise CompressionError(f"zstd decompression failed: {e}")

    elif extension == ".lz4":
        if not LZ4_AVAILABLE:
            raise ValueError(
                "lz4 decompression not available. Install: pip install lz4"
            )

        try:
            with open(file_path, "rb") as f_in:
                compressed = f_in.read()
                decompressed = lz4.frame.decompress(compressed)
                with open(output_path, "wb") as f_out:
                    f_out.write(decompressed)
        except Exception as e:
            raise CompressionError(f"lz4 decompression failed: {e}")

    else:
        raise ValueError(f"Unknown compression format: {extension}")

    # Remove compressed file if requested
    if remove_compressed and os.path.exists(output_path):
        os.remove(file_path)

    return output_path


def get_compression_ratio(original_path: str, compressed_path: str) -> float:
    """
    Calculate compression ratio.

    Args:
        original_path: Path to original file
        compressed_path: Path to compressed file

    Returns:
        Compression ratio (e.g., 0.5 means 50% of original size)
    """
    original_size = os.path.getsize(original_path)
    compressed_size = os.path.getsize(compressed_path)
    return compressed_size / original_size if original_size > 0 else 0


def get_compression_info() -> dict:
    """
    Get information about available compression algorithms.

    Returns:
        Dictionary with algorithm details
    """
    return {
        "gzip": {
            "available": True,
            "description": "Standard compression, good balance",
            "level_range": "1-9",
            "speed": "Moderate",
            "ratio": "Good",
        },
        "zstd": {
            "available": ZSTD_AVAILABLE,
            "description": "Facebook Zstandard, excellent all-around",
            "level_range": "1-22",
            "speed": "Fast",
            "ratio": "Excellent",
        },
        "lz4": {
            "available": LZ4_AVAILABLE,
            "description": "Very fast compression/decompression",
            "level_range": "1-12",
            "speed": "Very Fast",
            "ratio": "Moderate",
        },
    }
