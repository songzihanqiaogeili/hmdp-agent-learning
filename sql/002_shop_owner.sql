USE hmdp_agent;
-- Run once. Existing shops stay unassigned and cannot be edited by users.
ALTER TABLE shops ADD COLUMN owner_id BIGINT NULL COMMENT '???????ID';
CREATE INDEX idx_shops_owner_id ON shops (owner_id);
