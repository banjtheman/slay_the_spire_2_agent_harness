from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from live_bridge import BridgeApiError, LiveSts2Client

from .codex_cli import ClaudeCodeHarness, CodexCliHarness, CursorCliHarness, HarnessError
from .runner import AgentRunConfig, AgentRunner
from .state_prompt import compact_state_for_agent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m agent_harness",
        description="Run agent harnesses against the visible Slay the Spire 2 live bridge.",
    )
    parser.add_argument("--base-url", default="http://localhost:15526")
    parser.add_argument("--timeout", type=float, default=10.0)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check bridge and harness prerequisites")

    decide = sub.add_parser("decide", help="Ask a harness for one move from a state JSON file")
    _add_harness_args(decide)
    decide.add_argument("--state-file", required=True)
    decide.add_argument("--step", type=int, default=0)

    run = sub.add_parser("run", help="Run an agent loop against the visible game")
    _add_harness_args(run)
    run.add_argument("--max-steps", type=int, default=1)
    run.add_argument("--execute", action="store_true", help="Apply actions to the visible game")
    run.add_argument("--trace-dir", default="agent_runs")
    run.add_argument("--start-run", action="store_true")
    run.add_argument("--character", default="IRONCLAD")
    run.add_argument("--ascension", type=int, default=0)
    run.add_argument("--keep-going", action="store_true", help="Log errors instead of stopping")
    run.add_argument("--step-delay", type=float, default=0.2)
    run.add_argument("--encounter-notes-path", default=None)

    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "decide":
            harness = _make_harness(args)
            state = _read_json(args.state_file)
            decision = harness.decide(state, step=args.step, run_context={"mode": "decide"})
            _print({
                "decision": decision.to_trace(),
                "command_payload": decision.command_payload(),
            })
            return 0
        if args.command == "run":
            harness = _make_harness(args)
            config = AgentRunConfig(
                harness=args.harness,
                max_steps=args.max_steps,
                execute=args.execute,
                base_url=args.base_url,
                timeout=args.timeout,
                trace_dir=Path(args.trace_dir),
                start_run=args.start_run,
                character=args.character,
                ascension=args.ascension,
                stop_on_error=not args.keep_going,
                step_delay=args.step_delay,
                encounter_notes_path=Path(args.encounter_notes_path) if args.encounter_notes_path else None,
            )
            result = AgentRunner(config, harness).run()
            _print(result)
            return 0
    except (BridgeApiError, HarnessError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command {args.command}")
    return 2


def _add_harness_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--harness", default="codex-cli", choices=["codex-cli", "claude-code", "cursor-cli"])
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--cursor-bin", default="cursor-agent")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", default="medium", choices=["minimal", "low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--agent-workdir", default="agent_profiles/codex_base")
    parser.add_argument("--schema-path", default="agent_harness/action.schema.json")
    parser.add_argument("--sandbox", default="read-only", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--approval-policy", default="never", choices=["untrusted", "on-failure", "on-request", "never"])
    parser.add_argument("--agent-timeout", type=int, default=180)
    parser.add_argument("--allow-tools", action="store_true")
    parser.add_argument("--web-search", action="store_true")
    parser.add_argument("--no-ephemeral", action="store_true")
    parser.add_argument("--use-user-config", action="store_true")


def _make_harness(args: argparse.Namespace) -> CodexCliHarness | ClaudeCodeHarness | CursorCliHarness:
    if args.harness == "claude-code":
        return ClaudeCodeHarness(
            claude_bin=args.claude_bin,
            model=args.model or "sonnet",
            reasoning_effort=args.reasoning_effort,
            agent_workdir=Path(args.agent_workdir),
            schema_path=Path(args.schema_path),
            timeout_seconds=args.agent_timeout,
            allow_tools=args.allow_tools,
        )
    if args.harness == "cursor-cli":
        return CursorCliHarness(
            cursor_bin=args.cursor_bin,
            model=args.model or "composer-2.5-fast",
            agent_workdir=Path(args.agent_workdir),
            timeout_seconds=args.agent_timeout,
            allow_tools=args.allow_tools,
        )
    return CodexCliHarness(
        codex_bin=args.codex_bin,
        model=args.model or "gpt-5.5",
        reasoning_effort=args.reasoning_effort,
        agent_workdir=Path(args.agent_workdir),
        schema_path=Path(args.schema_path),
        sandbox=args.sandbox,
        approval_policy=args.approval_policy,
        timeout_seconds=args.agent_timeout,
        allow_tools=args.allow_tools,
        web_search=args.web_search,
        ephemeral=not args.no_ephemeral,
        ignore_user_config=not args.use_user_config,
    )


def _doctor(args: argparse.Namespace) -> int:
    codex_bin = shutil.which("codex")
    claude_bin = shutil.which("claude")
    cursor_bin = shutil.which("cursor-agent") or shutil.which("cursor")
    bridge = LiveSts2Client(base_url=args.base_url, timeout=args.timeout).doctor()
    _print({
        "codex_bin": codex_bin,
        "codex_cli_available": codex_bin is not None,
        "claude_bin": claude_bin,
        "claude_code_available": claude_bin is not None,
        "cursor_bin": cursor_bin,
        "cursor_cli_available": cursor_bin is not None,
        "bridge": bridge,
        "sample_commands": [
            "python -m agent_harness run --harness codex-cli --max-steps 1",
            "python -m agent_harness run --harness claude-code --model sonnet --max-steps 1",
            "python -m agent_harness run --harness cursor-cli --model composer-2.5-fast --max-steps 1",
        ],
    })
    return 0 if any((codex_bin, claude_bin, cursor_bin)) else 1


def _read_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("state file must contain a JSON object")
    return value


def _print(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
