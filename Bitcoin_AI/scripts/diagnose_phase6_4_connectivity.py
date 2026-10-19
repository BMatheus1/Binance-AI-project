from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.phase6_connectivity import diagnose_connectivity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnóstico somente leitura dos endpoints oficiais Binance Spot Demo")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 30:
        raise ValueError("timeout must be between 1 and 30 seconds")
    result = asyncio.run(diagnose_connectivity(ROOT, args.timeout))
    output = result
    if args.summary:
        output = {
            "checked_at": result["checked_at"], "environment": result["environment"],
            "public_connectivity_available": result["public_connectivity_available"],
            "authenticated_connectivity_available": result[
                "authenticated_connectivity_available"],
            "market_websocket_available": result["websockets"]["market_443"]["available"],
            "websocket_api_available": result["websockets"]["websocket_api"]["available"],
            "kill_switch_engaged": result["kill_switch"]["engaged"],
            "orders_sent": False,
        }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
