import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json

from .storage_provider import StorageProvider

# Lazy import for smbprotocol to avoid requirement if not used
try:
    import smbclient
    from smbclient import shutil as smbshutil

    SMB_AVAILABLE = True
except ImportError:
    SMB_AVAILABLE = False


class SMBStorage(StorageProvider):
    """
    Storage provider for SMB/CIFS shares (Windows/Samba)
    Uses smbprotocol library
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.server = config.get("server")
        self.share = config.get("share_name")
        self.username = config.get("smb_username")
        self.password = config.get("smb_password")
        self.domain = config.get("domain", "")
        # Optional: base path within the share
        self.base_path = config.get("remote_path", "").strip("/")

        if not all([self.server, self.share, self.username, self.password]):
            # Startups check might fail, but we raise error only on connection attempt
            pass

    def _register_session(self) -> None:
        """Register SMB session"""
        if not SMB_AVAILABLE:
            raise ImportError(
                "smbprotocol library not installed. Run: pip install smbprotocol"
            )

        try:
            smbclient.register_session(
                self.server,
                username=self.username,
                password=self.password,
                domain=self.domain if self.domain else None,
            )
        except Exception:
            # Session might already exist or connection failed
            # We'll let the actual operation fail if session is invalid
            # But let's look for specific error?
            # smbprotocol generally handles session pooling.
            pass

    def _get_full_path(self, remote_path: str) -> str:
        """Construct full UNC path"""
        # Format: \\server\share\base_path\remote_path
        # Normalize slashes
        path = f"\\\\{self.server}\\{self.share}"
        if self.base_path:
            path = f"{path}\\{self.base_path}"

        if remote_path:
            # Ensure remote_path doesn't start with / or \ to avoid double separator
            clean_remote = remote_path.lstrip("/\\")
            path = f"{path}\\{clean_remote}"

        # Ensure backslashes for Windows/SMB
        return path.replace("/", "\\")

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        dedup_ref_key: Optional[str] = None,
    ) -> bool:
        if not os.path.exists(local_path):
            print(f"File not found: {local_path}")
            return False

        self._register_session()
        full_path = self._get_full_path(remote_path)

        try:
            # Handle deduplication (copy from ref)
            if dedup_ref_key:
                ref_path = self._get_full_path(dedup_ref_key)
                try:
                    # Check if ref exists
                    if smbclient.path.exists(ref_path):
                        # Use copy
                        # Ensure parent dir exists
                        parent_dir = smbclient.path.dirname(full_path)
                        if not smbclient.path.exists(parent_dir):
                            smbclient.makedirs(parent_dir)

                        smbshutil.copyfile(ref_path, full_path)
                        print(f"✅ Deduplicated upload (copied from {dedup_ref_key})")
                        # We still need to save metadata? SMB doesn't natively support
                        # arbitrary xattrs easily across all servers.
                        # We will use a sidecar .metadata.json file for SMB
                        self._save_metadata(remote_path, metadata)
                        return True
                except Exception as e:
                    print(f"⚠️ Deduplication failed, falling back to upload: {e}")

            # Normal upload
            # Ensure parent dir exists
            parent_dir = smbclient.path.dirname(full_path)
            if not smbclient.path.exists(parent_dir):
                smbclient.makedirs(parent_dir)

            with open(local_path, "rb") as local_f:
                with smbclient.open_file(full_path, mode="wb") as remote_f:
                    shutil.copyfileobj(local_f, remote_f)

            self._save_metadata(remote_path, metadata)
            return True

        except Exception as e:
            print(f"❌ SMB Upload failed: {e}")
            return False

    def _save_metadata(
        self, remote_path: str, metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Save metadata in a sidecar json file"""
        if not metadata:
            return

        metadata_path = f"{remote_path}.metadata.json"
        full_path = self._get_full_path(metadata_path)

        try:
            with smbclient.open_file(full_path, mode="w") as f:
                json.dump(metadata, f)
        except Exception as e:
            print(f"⚠️ Failed to save metadata: {e}")

    def download_file(self, remote_path: str, local_path: str) -> bool:
        self._register_session()
        full_path = self._get_full_path(remote_path)

        try:
            with smbclient.open_file(full_path, mode="rb") as remote_f:
                with open(local_path, "wb") as local_f:
                    shutil.copyfileobj(remote_f, local_f)
            return True
        except Exception as e:
            print(f"❌ SMB Download failed: {e}")
            return False

    def delete_file(self, remote_path: str) -> bool:
        self._register_session()
        full_path = self._get_full_path(remote_path)

        try:
            if smbclient.path.exists(full_path):
                smbclient.remove(full_path)

                # Try delete metadata too
                meta_path = self._get_full_path(f"{remote_path}.metadata.json")
                if smbclient.path.exists(meta_path):
                    smbclient.remove(meta_path)

            return True
        except Exception as e:
            print(f"❌ SMB Delete failed: {e}")
            return False

    def list_files(
        self, prefix: str = "", max_keys: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        self._register_session()
        # Prefix is effectively a directory path for SMB
        # If prefix ends with /, treat as dir. If not, it's a filter?
        # S3 "prefix" usually implies directory-like structure.

        full_search_path = self._get_full_path(prefix)

        results = []
        try:
            if smbclient.path.isdir(full_search_path):
                # Iterate directory
                for filename in smbclient.listdir(full_search_path):
                    if filename.endswith(".metadata.json") or filename.endswith(
                        ".sha256"
                    ):
                        continue

                    file_path = smbclient.path.join(full_search_path, filename)
                    stat = smbclient.stat(file_path)

                    # Convert UNC path back to relative key?
                    # We need to return "key" which is `prefix/filename`
                    # careful with slashes
                    key = f"{prefix.rstrip('/')}/{filename}"

                    results.append(
                        {
                            "key": key,
                            "size": stat.st_size,
                            "last_modified": datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ),
                            "etag": "N/A",  # SMB doesn't have ETag
                        }
                    )
            else:
                # Maybe prefix lists a specific file or partial path?
                # Implementing deep recursive search like S3 is expensive on SMB.
                # We assume prefix corresponds to a folder for backups.
                pass

        except Exception as e:
            print(f"⚠️ SMB List failed: {e}")
            return []

        if max_keys:
            return results[:max_keys]
        return results

    def get_file_info(self, remote_path: str) -> Optional[Dict[str, Any]]:
        self._register_session()
        full_path = self._get_full_path(remote_path)

        try:
            stat = smbclient.stat(full_path)

            # Try load metadata
            metadata = {}
            meta_path = self._get_full_path(f"{remote_path}.metadata.json")
            if smbclient.path.exists(meta_path):
                try:
                    with smbclient.open_file(meta_path, "r") as f:
                        metadata = json.load(f)
                except Exception:
                    pass

            return {
                "key": remote_path,
                "size": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "content_type": "application/octet-stream",
                "metadata": metadata,
            }
        except Exception:
            return None

    def test_connection(self) -> bool:
        """Test SMB connection"""
        try:
            # Need to install smbprotocol first
            if not SMB_AVAILABLE:
                print("❌ smbprotocol library missing")
                return False

            self._register_session()

            # Try to list root share
            root_path = f"\\\\{self.server}\\{self.share}"
            smbclient.listdir(root_path)
            return True
        except Exception as e:
            print(f"❌ SMB Connection failed: {e}")
            return False
