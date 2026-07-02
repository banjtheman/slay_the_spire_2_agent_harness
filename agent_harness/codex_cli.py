from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .state_prompt import build_decision_prompt

JsonDict = dict[str, Any]
ACTION_ARG_KEYS = {
    "index",
    "option_index",
    "card_index",
    "target_index",
    "target",
    "slot",
    "potion_index",
    "relic_index",
    "indices",
    "col",
    "row",
    "character",
    "ascension",
    "seconds",
}


class HarnessError(RuntimeError):
    """Raised when an agent harness fails to produce a usable action."""


@dataclass
class AgentDecision:
    action: str
    args: JsonDict
    rationale: str
    expected: str = ""
    confidence: float | None = None
    tool_notes: list[str] = field(default_factory=list)
    raw_output: str = ""
    event_log: list[JsonDict] = field(default_factory=list)
    tool_events: list[JsonDict] = field(default_factory=list)
    usage: JsonDict = field(default_factory=dict)
    command: list[str] = field(default_factory=list)
    returncode: int = 0
    latency_ms: int = 0

    def command_payload(self) -> JsonDict:
        return {"cmd": "action", "action": self.action, "args": self.args}

    def to_trace(self) -> JsonDict:
        return {
            "action": self.action,
            "args": self.args,
            "rationale": self.rationale,
            "expected": self.expected,
            "confidence": self.confidence,
            "tool_notes": self.tool_notes,
            "raw_output": self.raw_output,
            "tool_events": self.tool_events,
            "usage": self.usage,
            "command": self.command,
            "returncode": self.returncode,
            "latency_ms": self.latency_ms,
        }


@dataclass
class CodexCliHarness:
    """Codex CLI harness: normalized game state in, action JSON out."""

    codex_bin: str = "codex"
    model: str | None = "gpt-5.5"
    reasoning_effort: str | None = "medium"
    agent_workdir: Path = Path("agent_profiles/codex_base")
    schema_path: Path = Path("agent_harness/action.schema.json")
    sandbox: str = "read-only"
    approval_policy: str = "never"
    timeout_seconds: int = 180
    allow_tools: bool = False
    web_search: bool = False
    ephemeral: bool = True
    ignore_user_config: bool = True
    extra_args: list[str] = field(default_factory=list)

    def decide(self, state: JsonDict, *, step: int, run_context: JsonDict | None = None) -> AgentDecision:
        prompt = build_decision_prompt(
            state,
            step=step,
            run_context=run_context or {},
            allow_tools=self.allow_tools,
        )
        command, last_message_path = self._build_command()
        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            cwd=str(self.agent_workdir),
            env=self._env(),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        event_log = _parse_jsonl(completed.stdout)
        raw_output = _read_last_message(last_message_path) or _final_message_from_events(event_log)
        if not raw_output:
            raw_output = completed.stdout.strip()
        if completed.returncode != 0:
            event_error = _error_from_events(event_log)
            raise HarnessError(
                "Codex CLI failed with exit code "
                f"{completed.returncode}: "
                f"{event_error or completed.stderr.strip() or completed.stdout[-1000:]}"
            )

        parsed = _extract_action_json(raw_output)
        action = str(parsed.get("action") or "").strip()
        if not action:
            raise HarnessError(f"Codex response did not include an action: {raw_output[:500]}")
        args = parsed.get("args")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise HarnessError(f"Codex action args must be an object: {raw_output[:500]}")
        args = _normalize_action_args(args)

        return AgentDecision(
            action=action,
            args=args,
            rationale=str(parsed.get("rationale") or ""),
            expected=str(parsed.get("expected") or ""),
            confidence=_optional_float(parsed.get("confidence")),
            tool_notes=_string_list(parsed.get("tool_notes")),
            raw_output=raw_output,
            event_log=event_log,
            tool_events=_summarize_tool_events(event_log),
            usage=_extract_usage(event_log),
            command=_redact_command(command),
            returncode=completed.returncode,
            latency_ms=latency_ms,
        )

    def _build_command(self) -> tuple[list[str], Path]:
        self.agent_workdir.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.resolve()
        if not schema.exists():
            raise HarnessError(f"Missing action schema: {schema}")
        output_file = Path(tempfile.NamedTemporaryFile(prefix="sts2-codex-", suffix=".json", delete=False).name)
        command = [
            self.codex_bin,
            "-s",
            self.sandbox,
            "-a",
            self.approval_policy,
        ]
        if self.web_search:
            command.append("--search")
        if self.model:
            command.extend(["--model", self.model])
        if self.reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{self.reasoning_effort}"'])
        command.extend([
            "exec",
            "--skip-git-repo-check",
            "--json",
            "--color",
            "never",
            "--output-last-message",
            str(output_file),
            "--output-schema",
            str(schema),
        ])
        if self.ephemeral:
            command.append("--ephemeral")
        if self.ignore_user_config:
            command.append("--ignore-user-config")
        command.extend(self.extra_args)
        command.append("-")
        return command, output_file

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        return env


@dataclass
class ClaudeCodeHarness:
    """Claude Code harness: normalized game state in, action JSON out."""

    claude_bin: str = "claude"
    model: str | None = "sonnet"
    reasoning_effort: str | None = "medium"
    agent_workdir: Path = Path("agent_profiles/codex_base")
    schema_path: Path = Path("agent_harness/action.schema.json")
    timeout_seconds: int = 180
    allow_tools: bool = False

    def decide(self, state: JsonDict, *, step: int, run_context: JsonDict | None = None) -> AgentDecision:
        prompt = build_decision_prompt(
            state,
            step=step,
            run_context=run_context or {},
            allow_tools=self.allow_tools,
        )
        command = self._build_command()
        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            cwd=str(self.agent_workdir),
            env=self._env(),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        event = _parse_json_object(completed.stdout)
        if completed.returncode != 0 or event.get("is_error"):
            raise HarnessError(
                "Claude Code failed with exit code "
                f"{completed.returncode}: "
                f"{event.get('result') or event.get('error') or completed.stderr.strip() or completed.stdout[-1000:]}"
            )
        structured = event.get("structured_output")
        raw_output = str(event.get("result") or "")
        parsed = structured if isinstance(structured, dict) else _extract_action_json(raw_output or completed.stdout)
        return _decision_from_parsed(
            parsed,
            raw_output=raw_output or json.dumps(parsed, ensure_ascii=False),
            event_log=[event],
            command=_redact_command(command),
            returncode=completed.returncode,
            latency_ms=latency_ms,
            usage=_normalize_claude_usage(event.get("usage")),
        )

    def _build_command(self) -> list[str]:
        self.agent_workdir.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.resolve()
        if not schema.exists():
            raise HarnessError(f"Missing action schema: {schema}")
        command = [
            self.claude_bin,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            schema.read_text(encoding="utf-8"),
            "--no-session-persistence",
        ]
        if self.model:
            command.extend(["--model", self.model])
        if self.reasoning_effort:
            command.extend(["--effort", _claude_effort(self.reasoning_effort)])
        if not self.allow_tools:
            command.extend(["--tools", ""])
        return command

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        return env


@dataclass
class CursorCliHarness:
    """Cursor Agent harness: normalized game state in, action JSON out."""

    cursor_bin: str = "cursor-agent"
    model: str | None = "gpt-5"
    agent_workdir: Path = Path("agent_profiles/codex_base")
    timeout_seconds: int = 180
    allow_tools: bool = False

    def decide(self, state: JsonDict, *, step: int, run_context: JsonDict | None = None) -> AgentDecision:
        prompt = build_decision_prompt(
            state,
            step=step,
            run_context=run_context or {},
            allow_tools=self.allow_tools,
        )
        command = self._build_command()
        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            cwd=str(self.agent_workdir),
            env=self._env(),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        event = _parse_json_object(completed.stdout)
        raw_output = _cursor_result_text(event) or completed.stdout.strip()
        if completed.returncode != 0:
            raise HarnessError(
                "Cursor Agent failed with exit code "
                f"{completed.returncode}: "
                f"{raw_output or completed.stderr.strip() or completed.stdout[-1000:]}"
            )
        parsed = _extract_action_json(raw_output)
        return _decision_from_parsed(
            parsed,
            raw_output=raw_output,
            event_log=[event] if event else [],
            command=_redact_command(command),
            returncode=completed.returncode,
            latency_ms=latency_ms,
            usage=_normalize_cursor_usage(event),
        )

    def _build_command(self) -> list[str]:
        self.agent_workdir.mkdir(parents=True, exist_ok=True)
        command = [
            self.cursor_bin,
            "-p",
            "--output-format",
            "json",
            "--trust",
            "--sandbox",
            "enabled",
        ]
        if not self.allow_tools:
            command.extend(["--mode", "ask"])
        if self.model:
            command.extend(["--model", self.model])
        return command

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        return env


def _decision_from_parsed(
    parsed: JsonDict,
    *,
    raw_output: str,
    event_log: list[JsonDict],
    command: list[str],
    returncode: int,
    latency_ms: int,
    usage: JsonDict | None = None,
) -> AgentDecision:
    action = str(parsed.get("action") or "").strip()
    if not action:
        raise HarnessError(f"Agent response did not include an action: {raw_output[:500]}")
    args = parsed.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise HarnessError(f"Agent action args must be an object: {raw_output[:500]}")
    args = _normalize_action_args(args)

    return AgentDecision(
        action=action,
        args=args,
        rationale=str(parsed.get("rationale") or ""),
        expected=str(parsed.get("expected") or ""),
        confidence=_optional_float(parsed.get("confidence")),
        tool_notes=_string_list(parsed.get("tool_notes")),
        raw_output=raw_output,
        event_log=event_log,
        tool_events=_summarize_tool_events(event_log),
        usage=usage or _extract_usage(event_log),
        command=command,
        returncode=returncode,
        latency_ms=latency_ms,
    )


def _parse_jsonl(text: str) -> list[JsonDict]:
    events: list[JsonDict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _parse_json_object(text: str) -> JsonDict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _read_last_message(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _final_message_from_events(events: list[JsonDict]) -> str:
    for event in reversed(events):
        for key in ("message", "content", "text"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        item = event.get("item")
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [part.get("text") for part in content if isinstance(part, dict)]
                text = "\n".join(part for part in parts if isinstance(part, str))
                if text.strip():
                    return text.strip()
    return ""


def _extract_action_json(text: str) -> JsonDict:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced = _extract_fenced_json(stripped)
    if fenced:
        return _extract_action_json(fenced)

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise HarnessError(f"Could not parse Codex response as JSON: {text[:800]}")


def _cursor_result_text(event: JsonDict) -> str:
    for key in ("result", "text", "message", "content", "response"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    item = event.get("item")
    if isinstance(item, dict):
        for key in ("result", "text", "message", "content"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _claude_effort(value: str) -> str:
    if value == "minimal":
        return "low"
    if value in {"low", "medium", "high", "xhigh"}:
        return value
    if value == "max":
        return "max"
    return "medium"


def _normalize_claude_usage(value: Any) -> JsonDict:
    if not isinstance(value, dict):
        return {}
    input_tokens = int(value.get("input_tokens") or 0)
    cache_creation = int(value.get("cache_creation_input_tokens") or 0)
    cache_read = int(value.get("cache_read_input_tokens") or 0)
    return {
        "input_tokens": input_tokens + cache_creation + cache_read,
        "cached_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "output_tokens": int(value.get("output_tokens") or 0),
        "reasoning_output_tokens": 0,
    }


def _normalize_cursor_usage(event: JsonDict) -> JsonDict:
    usage = event.get("usage") if isinstance(event, dict) else None
    if not isinstance(usage, dict):
        return {}
    result: JsonDict = {}
    for source, target in (
        ("input_tokens", "input_tokens"),
        ("inputTokens", "input_tokens"),
        ("cached_input_tokens", "cached_input_tokens"),
        ("cachedInputTokens", "cached_input_tokens"),
        ("output_tokens", "output_tokens"),
        ("outputTokens", "output_tokens"),
        ("reasoning_output_tokens", "reasoning_output_tokens"),
        ("reasoningOutputTokens", "reasoning_output_tokens"),
    ):
        if source in usage and isinstance(usage[source], (int, float)):
            result[target] = int(result.get(target) or 0) + int(usage[source])
    return result


def _extract_fenced_json(text: str) -> str:
    fence = "```"
    start = text.find(fence)
    if start == -1:
        return ""
    body_start = text.find("\n", start + len(fence))
    if body_start == -1:
        return ""
    end = text.find(fence, body_start + 1)
    if end == -1:
        return ""
    return text[body_start + 1:end].strip()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _normalize_action_args(args: JsonDict) -> JsonDict:
    return {str(key): value for key, value in args.items() if key in ACTION_ARG_KEYS and value is not None}


def _summarize_tool_events(events: list[JsonDict]) -> list[JsonDict]:
    summaries: list[JsonDict] = []
    for event in events:
        event_type = str(event.get("type") or "").lower()
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type") or "").lower()
        if not any(token in event_type for token in ("tool", "exec", "call", "command")) and not any(
            token in item_type for token in ("tool", "exec", "call", "command")
        ):
            continue
        summaries.append(_truncate_json(event, max_chars=2000))
    return summaries


def _extract_usage(events: list[JsonDict]) -> JsonDict:
    for event in reversed(events):
        usage = event.get("usage")
        if isinstance(usage, dict):
            return {str(key): value for key, value in usage.items() if isinstance(value, (int, float))}
    return {}


def _error_from_events(events: list[JsonDict]) -> str:
    for event in reversed(events):
        if event.get("type") not in {"error", "turn.failed"}:
            continue
        message = event.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        error = event.get("error")
        if isinstance(error, dict):
            nested = error.get("message")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
            return json.dumps(error, ensure_ascii=False)
    return ""


def _truncate_json(value: Any, *, max_chars: int) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_chars:
        return value
    return {"truncated": text[:max_chars] + "..."}


def _redact_command(command: list[str]) -> list[str]:
    redacted = list(command)
    for flag in ("--json-schema", "--api-key"):
        try:
            index = redacted.index(flag)
        except ValueError:
            continue
        if index + 1 < len(redacted):
            redacted[index + 1] = "<redacted>"
    return redacted
