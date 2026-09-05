from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import ContractError, compile_engagement
from .render import write_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile enterprise requirements into a qualified solution decision")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("generated"))
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text())
        result = compile_engagement(payload)
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        parser.error(str(exc))
    write_outputs(result, args.output)
    print(json.dumps({"status": result["status"], "selected_option": result["selected_option"], "evidence_digest": result["evidence_digest"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
