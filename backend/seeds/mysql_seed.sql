-- Sample schema and data for MySQL test database

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    product_id INT,
    qty INT NOT NULL DEFAULT 1,
    total DECIMAL(10, 2) NOT NULL,
    ordered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT IGNORE INTO users (name, email) VALUES
    ('Alice Rossi', 'alice@example.com'),
    ('Bob Bianchi', 'bob@example.com'),
    ('Clara Verdi', 'clara@example.com'),
    ('Dario Neri', 'dario@example.com'),
    ('Elena Gallo', 'elena@example.com'),
    ('Fabio Esposito', 'fabio@example.com'),
    ('Giada Ferrara', 'giada@example.com'),
    ('Hiro Tanaka', 'hiro@example.com'),
    ('Iris Kohl', 'iris@example.com'),
    ('Jakub Nowak', 'jakub@example.com'),
    ('Katia Moretti', 'katia@example.com'),
    ('Luca Russo', 'luca@example.com'),
    ('Marta Costa', 'marta@example.com'),
    ('Nico Ricci', 'nico@example.com'),
    ('Olga Petrov', 'olga@example.com'),
    ('Paolo Bruno', 'paolo@example.com'),
    ('Qian Li', 'qian@example.com'),
    ('Rosa Marino', 'rosa@example.com'),
    ('Sara Conte', 'sara@example.com'),
    ('Tomas Novak', 'tomas@example.com');

INSERT IGNORE INTO products (name, price, stock) VALUES
    ('Laptop Pro 15"', 1299.99, 45),
    ('Wireless Mouse', 29.99, 200),
    ('Mechanical Keyboard', 89.99, 120),
    ('27" Monitor', 399.99, 30),
    ('USB-C Hub', 49.99, 150),
    ('Webcam HD 1080p', 79.99, 80),
    ('Noise-Cancelling Headphones', 249.99, 60),
    ('External SSD 1TB', 109.99, 90),
    ('Standing Desk Mat', 39.99, 110),
    ('Cable Management Kit', 19.99, 300),
    ('Laptop Stand', 34.99, 175),
    ('Ergonomic Chair', 499.99, 20),
    ('Desk Lamp LED', 44.99, 130),
    ('Portable Charger 20000mAh', 59.99, 95),
    ('Smart Speaker', 129.99, 55),
    ('Drawing Tablet', 199.99, 35),
    ('Wi-Fi 6 Router', 179.99, 40),
    ('Raspberry Pi 4', 64.99, 70),
    ('Arduino Starter Kit', 49.99, 85),
    ('3D Printer Filament PLA', 24.99, 500);

INSERT INTO orders (user_id, product_id, qty, total) VALUES
    (1, 1, 1, 1299.99),
    (2, 2, 2, 59.98),
    (3, 3, 1, 89.99),
    (4, 4, 1, 399.99),
    (5, 5, 3, 149.97),
    (6, 6, 1, 79.99),
    (7, 7, 1, 249.99),
    (8, 8, 2, 219.98),
    (9, 9, 1, 39.99),
    (10, 10, 4, 79.96),
    (11, 11, 1, 34.99),
    (12, 12, 1, 499.99),
    (13, 13, 2, 89.98),
    (14, 14, 1, 59.99),
    (15, 15, 1, 129.99),
    (16, 16, 1, 199.99),
    (17, 17, 1, 179.99),
    (18, 18, 2, 129.98),
    (19, 19, 1, 49.99),
    (20, 20, 5, 124.95);
