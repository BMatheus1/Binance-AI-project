import argparse
from pathlib import Path

from btc_research.phase5 import import_colab_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa resultados Kronos produzidos pelo notebook da Fase 5")
    parser.add_argument("source", type=Path, help="pasta com run_manifest.json e kronos_predictions.parquet")
    args = parser.parse_args()
    print(import_colab_results(args.source))


if __name__ == "__main__":
    main()
