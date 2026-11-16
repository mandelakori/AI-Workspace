import argparse
import json
from dataclasses import asdict

from .model import QuoteRequest
from .service import quote


def main(argv=None):
    cli = argparse.ArgumentParser(description="Quote a parcel in cents.")
    cli.add_argument("--grams", type=int, required=True)
    args = cli.parse_args(argv)
    try:
        result = quote(QuoteRequest(args.grams))
    except ValueError as exc:
        cli.error(str(exc))
    print(json.dumps(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
