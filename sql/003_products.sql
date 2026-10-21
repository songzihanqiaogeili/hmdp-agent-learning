USE hmdp_agent;

CREATE TABLE IF NOT EXISTS products (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(2000) NOT NULL DEFAULT '',
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    status TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_products_shop_status_id (shop_id, status, id),
    CONSTRAINT fk_products_shop FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT chk_products_price CHECK (price > 0),
    CONSTRAINT chk_products_stock CHECK (stock >= 0),
    CONSTRAINT chk_products_status CHECK (status IN (0, 1))
);
