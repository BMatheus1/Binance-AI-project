import argparse
import logging

from .common import ROOT


def main():
    parser = argparse.ArgumentParser(description="BTCUSDT: pesquisa local sem execução de ordens")
    parser.add_argument("command", choices=["audit", "knowledge", "ingest", "features", "pilot", "train", "evaluate", "reports"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "audit":
        from .audit import audit
        audit()
    elif args.command == "knowledge":
        from .knowledge import index_books
        index_books()
    elif args.command == "ingest":
        from .ingestion import ingest
        ingest()
    elif args.command == "features":
        from .features import build
        build()
    elif args.command in {"train", "pilot"}:
        from .training import evaluate, train
        run = train(pilot=args.command == "pilot")
        print(run)
        if args.command == "pilot":
            evaluate(run=run)
    elif args.command == "evaluate":
        from .training import evaluate
        evaluate()
    elif args.command == "reports":
        from .reporting import report_all
        report_all()


if __name__ == "__main__":
    main()
