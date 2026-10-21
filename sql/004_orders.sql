USE hmdp_agent;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    shop_id BIGINT NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    idempotency_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_orders_user_key (user_id, idempotency_key),
    INDEX idx_orders_user_id (user_id, id),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT fk_orders_shop FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT chk_orders_quantity CHECK (quantity BETWEEN 1 AND 99),
    CONSTRAINT chk_orders_unit_price CHECK (unit_price > 0),
    CONSTRAINT chk_orders_total CHECK (total_amount = unit_price * quantity)
);
