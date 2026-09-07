from __future__ import annotations

import argparse
import json
from pathlib import Path

from .qualification import QualificationError, qualify


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify a technical opportunity before solution engineering")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-pursue", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text())
        result = qualify(payload)
    except (OSError, json.JSONDecodeError, QualificationError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "decision": result["decision"],
        "qualification_score": result["qualification_score"],
        "unresolved_questions": len(result["customer_questions"]),
        "output": str(args.output),
    }, indent=2))
    return 2 if args.require_pursue and result["decision"] != "PURSUE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
