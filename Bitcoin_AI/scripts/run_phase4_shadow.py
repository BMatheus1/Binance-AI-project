"""Executa observação pública em shadow; este script não contém envio de ordens."""
import argparse
import asyncio
import json

from btc_research.phase4_live import run_shadow


def main() -> None:
    parser = argparse.ArgumentParser(description="Observador público shadow da Fase 4")
    parser.add_argument("--seconds", type=float, default=370,
                        help="duração da coleta em segundos (padrão: 370)")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds deve ser positivo")
    print(json.dumps(asyncio.run(run_shadow(args.seconds)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
