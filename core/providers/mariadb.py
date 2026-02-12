"""MariaDB database provider (uses MySQL protocol)"""

from .mysql import MySQLProvider


class MariaDBProvider(MySQLProvider):
    """
    MariaDB backup and restore provider

    MariaDB uses the MySQL wire protocol and tools (mysqldump/mysql),
    so we inherit from MySQLProvider with no changes needed.

    This separate class exists for:
    1. Clear provider identification in configs
    2. Future MariaDB-specific features if needed
    3. Better user experience (users know it's explicitly supported)
    """

    def __init__(self, db_config: dict) -> None:
        super().__init__(db_config)

    # All methods inherited from MySQLProvider:
    # - test_connection()
    # - backup()
    # - restore()

    # MariaDB-specific methods can be added here in the future
    # For example: specific optimizations, version checks, etc.
