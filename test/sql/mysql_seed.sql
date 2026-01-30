CREATE TABLE IF NOT EXISTS test_table (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

TRUNCATE test_table;

INSERT INTO test_table (name, data) VALUES 
('Setup', 'Initial test data for MySQL'),
('Version', '1.0.0');
