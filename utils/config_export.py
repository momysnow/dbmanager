"""Configuration export and import utilities"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import zipfile
import tempfile

from config import ConfigManager, CONFIG_DIR, CONFIG_FILE


class ConfigExporter:
    """Export and import configuration"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def export_config(self, output_path: str = None, include_backups: bool = False) -> str:
        """
        Export configuration to a file
        
        Args:
            output_path: Path to export file (default: ~/dbmanager-export-TIMESTAMP.zip)
            include_backups: Include backup files in export
        
        Returns:
            Path to exported file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / f"dbmanager-export-{timestamp}.zip"
        else:
            output_path = Path(output_path)
        
        # Create temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy config.json
            config_export = temp_path / "config.json"
            shutil.copy2(CONFIG_FILE, config_export)
            
            # Create export metadata
            metadata = {
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "includes_backups": include_backups
            }
            
            with open(temp_path / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Include backups if requested
            if include_backups:
                backups_dir = CONFIG_DIR / "backups"
                if backups_dir.exists():
                    export_backups = temp_path / "backups"
                    shutil.copytree(backups_dir, export_backups)
            
            # Create zip file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in temp_path.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(temp_path)
                        zipf.write(file, arcname)
        
        return str(output_path)
    
    def import_config(self, import_path: str, merge: bool = False, restore_backups: bool = False) -> Dict[str, Any]:
        """
        Import configuration from a file
        
        Args:
            import_path: Path to import file
            merge: Merge with existing config (default: replace)
            restore_backups: Restore backup files from export
        
        Returns:
            Import summary
        """
        import_path = Path(import_path)
        
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")
        
        summary = {
            "databases_imported": 0,
            "s3_buckets_imported": 0,
            "schedules_imported": 0,
            "backups_restored": 0,
            "errors": []
        }
        
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract zip file
            with zipfile.ZipFile(import_path, 'r') as zipf:
                zipf.extractall(temp_path)
            
            # Read metadata
            metadata_file = temp_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            # Read imported config
            config_file = temp_path / "config.json"
            if not config_file.exists():
                raise ValueError("Invalid export file: config.json not found")
            
            with open(config_file, 'r') as f:
                imported_config = json.load(f)
            
            # Import configuration
            if merge:
                # Merge configurations
                current_config = self.config_manager.config
                
                # Merge databases
                existing_db_names = {db['name'] for db in current_config.get('databases', [])}
                for db in imported_config.get('databases', []):
                    if db['name'] not in existing_db_names:
                        # Assign new ID
                        db_copy = db.copy()
                        db_copy.pop('id', None)
                        self.config_manager.add_database(db_copy)
                        summary['databases_imported'] += 1
                
                # Merge S3 buckets
                existing_bucket_names = {b['name'] for b in current_config.get('s3_buckets', [])}
                s3_buckets = current_config.get('s3_buckets', [])
                for bucket in imported_config.get('s3_buckets', []):
                    if bucket['name'] not in existing_bucket_names:
                        bucket_copy = bucket.copy()
                        bucket_copy['id'] = max([b.get('id', 0) for b in s3_buckets] + [0]) + 1
                        s3_buckets.append(bucket_copy)
                        summary['s3_buckets_imported'] += 1
                
                current_config['s3_buckets'] = s3_buckets
                
                # Merge schedules (skip to avoid duplicates)
                # Merge global settings (take imported)
                if 'global_settings' in imported_config:
                    current_config['global_settings'] = imported_config['global_settings']
                
                # Merge notifications (take imported)
                if 'notifications' in imported_config:
                    current_config['notifications'] = imported_config['notifications']
                
                self.config_manager.config = current_config
                self.config_manager.save_config()
            else:
                # Replace configuration
                summary['databases_imported'] = len(imported_config.get('databases', []))
                summary['s3_buckets_imported'] = len(imported_config.get('s3_buckets', []))
                summary['schedules_imported'] = len(imported_config.get('schedules', []))
                
                self.config_manager.config = imported_config
                self.config_manager.save_config()
            
            # Restore backups if requested
            if restore_backups and metadata.get('includes_backups'):
                backups_source = temp_path / "backups"
                if backups_source.exists():
                    backups_dest = CONFIG_DIR / "backups"
                    
                    # Copy backups
                    for db_dir in backups_source.iterdir():
                        if db_dir.is_dir():
                            dest_dir = backups_dest / db_dir.name
                            dest_dir.mkdir(parents=True, exist_ok=True)
                            
                            for backup_file in db_dir.iterdir():
                                if backup_file.is_file():
                                    shutil.copy2(backup_file, dest_dir / backup_file.name)
                                    summary['backups_restored'] += 1
        
        return summary
    
    def export_to_json(self, output_path: str = None) -> str:
        """
        Export configuration to a JSON file (config only, no backups)
        
        Args:
            output_path: Path to export file
        
        Returns:
            Path to exported file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / f"dbmanager-config-{timestamp}.json"
        else:
            output_path = Path(output_path)
        
        # Copy config with metadata
        export_data = {
            "export_date": datetime.now().isoformat(),
            "version": "1.0",
            "config": self.config_manager.config
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return str(output_path)
    
    def import_from_json(self, import_path: str, merge: bool = False) -> Dict[str, Any]:
        """
        Import configuration from a JSON file
        
        Args:
            import_path: Path to import file
            merge: Merge with existing config
        
        Returns:
            Import summary
        """
        import_path = Path(import_path)
        
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")
        
        with open(import_path, 'r') as f:
            import_data = json.load(f)
        
        # Extract config
        if 'config' in import_data:
            imported_config = import_data['config']
        else:
            # Assume direct config format
            imported_config = import_data
        
        # Use regular import logic
        summary = {
            "databases_imported": len(imported_config.get('databases', [])),
            "s3_buckets_imported": len(imported_config.get('s3_buckets', [])),
            "schedules_imported": len(imported_config.get('schedules', [])),
            "backups_restored": 0,
            "errors": []
        }
        
        if not merge:
            self.config_manager.config = imported_config
            self.config_manager.save_config()
        
        return summary
