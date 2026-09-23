import argparse
import json
from pathlib import Path

from .private_inference import OfferError, compile_offer, write_offer


def main() -> int:
    parser = argparse.ArgumentParser(description="Price and prepare a private inference delivery offer")
    parser.add_argument("intake", type=Path)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path, default=Path("generated/private-inference"))
    args = parser.parse_args()
    try:
        offer = compile_offer(json.loads(args.intake.read_text()),
                              json.loads(args.benchmark.read_text()))
        write_offer(offer, args.output)
    except (OSError, json.JSONDecodeError, OfferError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": offer["status"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
