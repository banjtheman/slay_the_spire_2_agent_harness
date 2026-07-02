from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .client import BridgeApiError, LiveSts2Client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m live_bridge",
        description="Control the visible Slay the Spire 2 game through STS2_Bridge.",
    )
    parser.add_argument("--base-url", default="http://localhost:15526")
    parser.add_argument("--timeout", type=float, default=10.0)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check bridge connectivity")
    sub.add_parser("state", help="Print normalized state")
    sub.add_parser("raw-state", help="Print raw bridge state")

    start = sub.add_parser("start-run", help="Start a new visible-game run")
    start.add_argument("--character", default="IRONCLAD")
    start.add_argument("--ascension", type=int, default=0)

    action = sub.add_parser("action", help="Send a live action")
    action.add_argument("name")
    action.add_argument("--arg", action="append", default=[], help="key=value payload entries")

    send_json = sub.add_parser("send-json", help="Send a headless-style JSON command")
    send_json.add_argument("json_command")

    repl = sub.add_parser("repl", help="Read JSON commands from stdin and write JSON states")
    repl.add_argument("--stop-on-error", action="store_true")

    args = parser.parse_args(argv)
    client = LiveSts2Client(base_url=args.base_url, timeout=args.timeout)

    try:
        if args.command == "doctor":
            _print(client.doctor())
        elif args.command == "state":
            _print(client.state())
        elif args.command == "raw-state":
            _print(client.raw_state(format="json"))
        elif args.command == "start-run":
            _print(client.send({
                "cmd": "start_run",
                "character": args.character,
                "ascension": args.ascension,
            }))
        elif args.command == "action":
            _print(client.send_action(args.name, **_parse_pairs(args.arg)))
        elif args.command == "send-json":
            command = json.loads(args.json_command)
            if not isinstance(command, dict):
                raise ValueError("JSON command must be an object")
            _print(client.send(command))
        elif args.command == "repl":
            return _run_repl(client, stop_on_error=args.stop_on_error)
        else:
            parser.error(f"unknown command {args.command}")
    except (BridgeApiError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


def _run_repl(client: LiveSts2Client, *, stop_on_error: bool) -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            command = json.loads(line)
            if not isinstance(command, dict):
                raise ValueError("JSON command must be an object")
            _print(client.send(command))
        except Exception as exc:  # Keep long agent runs alive unless requested.
            _print({"type": "error", "message": str(exc)})
            if stop_on_error:
                return 1
    return 0


def _parse_pairs(entries: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Expected key=value, got {entry!r}")
        key, raw = entry.split("=", 1)
        result[key] = _coerce(raw)
    return result


def _coerce(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _print(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())

