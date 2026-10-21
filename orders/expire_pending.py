"""一次性扫描命令；本身不是常驻定时任务。"""
import argparse
import json

from orders.service import expire_pending_orders


def main() -> None:
    parser = argparse.ArgumentParser(description="关闭超时待支付订单，幂等返还库存")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000 or not 1 <= args.max_batches <= 1000:
        parser.error("batch-size 和 max-batches 必须在 1 到 1000 之间")
    summary = expire_pending_orders(args.batch_size, args.max_batches)
    print(json.dumps(summary))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
