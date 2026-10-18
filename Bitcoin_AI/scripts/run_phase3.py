import argparse
import logging

from btc_research.common import ROOT
from btc_research.microstructure import download_pilot, ingest_pilot
from btc_research.phase3 import run


def main():
    parser = argparse.ArgumentParser(description="Executa o piloto oficial e exploratório da Fase 3")
    parser.add_argument("stage", choices=["download", "ingest", "experiment", "all"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.stage in {"download", "all"}:
        logging.info("Download/checksum: %s", download_pilot(ROOT))
    if args.stage in {"ingest", "all"}:
        logging.info("Ingestão: %s", ingest_pilot(ROOT))
    if args.stage in {"experiment", "all"}:
        logging.info("Resultados: %s", run(ROOT))


if __name__ == "__main__":
    main()
