# 本地测试数据

先启动 MySQL。需要一并生成测试登录 Token 时，还需 Redis。

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo --login
```

在 VS Code 打开 `.local/demo-data.json`，查看两个账号、商铺和商品 ID。
打开 `.local/demo-tokens.json`，复制账号 A 或 B 的 `access_token` 到 Swagger 的 Authorize。
这些 Token 使用现有的登录业务生成，默认有效期 2 小时。过期后重新加 `--login` 运行即可。
文件夹 `.local/` 已被 Git 忽略，不要把凭证复制到公开文档或提交中。

| 场景 | 初始状态 | 购买数量 | 初始库存 | 可以验证什么 |
|---|---|---|---|---|
| pending | pending | 2 | 18 | 支付或取消 |
| paid | paid | 2 | 18 | 重复支付不重复扣库存、取消被拒绝 |
| cancelled | cancelled | 2 | 20 | 重复取消不重复返库存 |
| expired | expired | 2 | 20 | 再取消/支付被拒绝、库存不再增加 |
| due | pending，但已过期 | 2 | 18 | 支付时主动关单或运行超时扫描 |
| b_pending | B 的待支付订单 | 2 | 18 | A 查看或取消 B 的订单返回 404 |

每个订单场景使用独立商品。另有 A/B 各一个库存 100 的已上架商品，可自由下单。

脚本使用真实 SQL 与同一事务创建订单和调整库存，不会仅修改订单状态造出错误库存。
通过 `demo_seed_registry` 登记专属记录；手机号若已被非脚本账号使用，会停止而非接管。
重复运行同一批次保留已经修改的状态和库存；pending 订单仍遵循实际 15 分钟支付期限，
不会因为重新运行脚本而续期。需要全新场景时使用新批次名：

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo --set demo-v2 --login
```

同一个批次可重复运行，不增加重复记录；不同批次会增加一套新的场景，两个账号会复用。
当前仍允许已登录用户创建商铺，这是学习版资源归属模型，还未增加商家入驻审核。
脚本只用于本地开发，不新增 HTTP 绕过登录接口，也不会发送真实短信。

超时扫描会处理库中所有符合条件的订单，不只处理这套测试数据：

```powershell
.\.venv\Scripts\python.exe -m orders.expire_pending
```

模拟支付需 `.env` 中的 `ENABLE_MOCK_PAYMENT=true`，修改配置后重启后端。
