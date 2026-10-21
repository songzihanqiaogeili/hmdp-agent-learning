USE hmdp_agent;

-- 按迁移顺序执行一次。历史订单补齐原创建时间后 15 分钟的支付期限。
ALTER TABLE orders ADD COLUMN expires_at DATETIME NULL;
UPDATE orders SET expires_at = DATE_ADD(created_at, INTERVAL 15 MINUTE)
WHERE expires_at IS NULL;
ALTER TABLE orders MODIFY COLUMN expires_at DATETIME NOT NULL;
CREATE INDEX idx_orders_status_expiry ON orders (status, expires_at, id);
