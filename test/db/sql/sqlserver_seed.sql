IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='test_table' AND xtype='U')
BEGIN
    CREATE TABLE test_table (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(100),
        data NVARCHAR(MAX),
        created_at DATETIME DEFAULT GETDATE()
    )
END

TRUNCATE TABLE test_table;

INSERT INTO test_table (name, data) VALUES 
('Setup', 'Initial test data for SQL Server'),
('Version', '1.0.0');
