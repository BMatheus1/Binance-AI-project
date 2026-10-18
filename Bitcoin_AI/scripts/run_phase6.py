from __future__ import annotations

import argparse
import asyncio
import json

from btc_research.common import ROOT, save_json
from btc_research.phase6 import MultiAssetMarketService, build_news_service, prepare


async def main_async(args) -> None:
    if args.command == "prepare":
        print(prepare(ROOT))
        return
    if args.command == "news-once":
        result = await build_news_service(ROOT).cycle()
        save_json(ROOT / "reports/phase_6/news_smoke.json", result)
        print(json.dumps(result, indent=2))
        return
    if args.command == "observe-market":
        service = MultiAssetMarketService(ROOT)
        result = await service.run(duration_seconds=args.seconds)
        save_json(ROOT / "reports/phase_6/market_smoke.json", result)
        print(json.dumps(result, indent=2))
        return
    if args.command == "serve-news":
        service = build_news_service(ROOT)
        try:
            await service.serve()
        finally:
            service.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6 observation/paper services; no real trading")
    parser.add_argument("command", choices=["prepare", "news-once", "serve-news", "observe-market"])
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
