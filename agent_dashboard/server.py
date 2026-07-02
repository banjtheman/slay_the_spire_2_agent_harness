from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import threading
import time
import traceback
import urllib.parse
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agent_harness.codex_cli import ClaudeCodeHarness, CodexCliHarness, CursorCliHarness
from agent_harness.runner import AgentRunConfig, AgentRunner
from agent_harness.state_prompt import compact_state_for_agent
from live_bridge import LiveSts2Client

JsonDict = dict[str, Any]

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
HARNESS_DEFAULT_MODELS = {
    "codex-cli": "gpt-5.5",
    "claude-code": "sonnet",
    "cursor-cli": "composer-2.5-fast",
}
HARNESS_DEFAULT_PRICING = {
    "codex-cli": {"input": 5.0, "cached": 0.5, "output": 30.0},
    "claude-code": {"input": 3.0, "cached": 0.3, "output": 15.0},
    "cursor-cli": {"input": 0.5, "cached": 0.0, "output": 2.5},
}


@dataclass
class DashboardJob:
    id: str
    config: JsonDict
    created_at: float = field(default_factory=time.time)
    status: str = "queued"
    trace_path: str | None = None
    result: JsonDict | None = None
    error: str | None = None
    traceback_text: str | None = None
    finished_at: float | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def public(self) -> JsonDict:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "trace_path": self.trace_path,
            "config": self.config,
            "result": self.result,
            "error": self.error,
        }


class DashboardState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.jobs: dict[str, DashboardJob] = {}
        self.latest_id: str | None = None

    def add(self, job: DashboardJob) -> None:
        with self.lock:
            self.jobs[job.id] = job
            self.latest_id = job.id

    def get(self, job_id: str) -> DashboardJob | None:
        with self.lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> list[JsonDict]:
        with self.lock:
            return [job.public() for job in sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)]

    def running_job(self) -> DashboardJob | None:
        with self.lock:
            for job in self.jobs.values():
                if job.status in {"queued", "running", "stopping"}:
                    return job
        return None


STATE = DashboardState()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Slay the Spire 2 agent harness dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Agent dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "STS2AgentDashboard/0.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self._handle_status()
            return
        if parsed.path == "/api/profiles":
            self._handle_profiles_list()
            return
        if parsed.path == "/api/profile":
            self._handle_profile_get(parsed)
            return
        if parsed.path == "/api/runs":
            self._json({"runs": STATE.list_jobs()})
            return
        if parsed.path.startswith("/api/runs/"):
            self._handle_run_get(parsed)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/profile":
            self._handle_profile_save()
            return
        if parsed.path == "/api/runs":
            self._handle_run_start()
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/stop"):
            self._handle_run_stop(parsed.path)
            return
        self._json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _handle_status(self) -> None:
        client = LiveSts2Client()
        bridge = client.doctor()
        current_state: JsonDict | None = None
        if bridge.get("ok"):
            try:
                current_state = compact_state_for_agent(client.state())
            except Exception:
                current_state = None
        self._json({
            "bridge": bridge,
            "current_state": current_state,
            "codex_bin": shutil.which("codex"),
            "claude_bin": shutil.which("claude"),
            "cursor_bin": shutil.which("cursor-agent") or shutil.which("cursor"),
            "runs": STATE.list_jobs()[:8],
        })

    def _handle_profiles_list(self) -> None:
        profiles_root = ROOT / "agent_profiles"
        profiles = []
        if profiles_root.exists():
            for profile_dir in sorted(path for path in profiles_root.iterdir() if path.is_dir()):
                agents_path = profile_dir / "AGENTS.md"
                if not agents_path.exists():
                    continue
                profiles.append({
                    "name": profile_dir.name,
                    "label": _profile_label(profile_dir.name),
                    "agent_workdir": str(profile_dir.relative_to(ROOT)),
                    "agents_path": str(agents_path.relative_to(ROOT)),
                })
        self._json({"profiles": profiles})

    def _handle_profile_get(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        try:
            profile_dir = _resolve_profile_dir(params.get("agent_workdir", ["agent_profiles/codex_base"])[0])
        except ValueError as exc:
            self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        agents_path = profile_dir / "AGENTS.md"
        if not agents_path.exists():
            self._json({"error": "AGENTS.md not found for selected profile"}, status=HTTPStatus.NOT_FOUND)
            return
        self._json({
            "profile": {
                "name": profile_dir.name,
                "label": _profile_label(profile_dir.name),
                "agent_workdir": str(profile_dir.relative_to(ROOT)),
                "agents_path": str(agents_path.relative_to(ROOT)),
                "agents_md": agents_path.read_text(encoding="utf-8"),
            }
        })

    def _handle_profile_save(self) -> None:
        body = self._read_json()
        try:
            profile_dir = _resolve_profile_dir(str(body.get("agent_workdir") or "agent_profiles/codex_base"))
        except ValueError as exc:
            self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        agents_md = body.get("agents_md")
        if not isinstance(agents_md, str):
            self._json({"error": "agents_md must be a string"}, status=HTTPStatus.BAD_REQUEST)
            return
        agents_path = profile_dir / "AGENTS.md"
        if not agents_path.exists():
            self._json({"error": "AGENTS.md not found for selected profile"}, status=HTTPStatus.NOT_FOUND)
            return
        agents_path.write_text(agents_md.rstrip() + "\n", encoding="utf-8")
        self._json({
            "profile": {
                "name": profile_dir.name,
                "label": _profile_label(profile_dir.name),
                "agent_workdir": str(profile_dir.relative_to(ROOT)),
                "agents_path": str(agents_path.relative_to(ROOT)),
                "saved_at": time.time(),
            }
        })

    def _handle_run_start(self) -> None:
        running = STATE.running_job()
        if running is not None:
            self._json({"error": "a run is already active", "run": running.public()}, status=HTTPStatus.CONFLICT)
            return

        body = self._read_json()
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        config = _normalize_run_config(body)
        job = DashboardJob(id=run_id, config=config)
        STATE.add(job)
        job.thread = threading.Thread(target=_run_job, args=(job,), name=f"agent-run-{run_id}", daemon=True)
        job.thread.start()
        self._json({"run": job.public()}, status=HTTPStatus.CREATED)

    def _handle_run_get(self, parsed: urllib.parse.ParseResult) -> None:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 3:
            self._json({"error": "missing run id"}, status=HTTPStatus.BAD_REQUEST)
            return
        job = STATE.get(parts[2])
        if job is None:
            self._json({"error": "run not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if len(parts) == 4 and parts[3] == "events":
            offset = int(urllib.parse.parse_qs(parsed.query).get("offset", ["0"])[0] or 0)
            self._json(_read_trace_events(job.trace_path, offset=offset, pricing=job.config.get("pricing")))
            return
        self._json({"run": job.public(), "summary": _summarize_trace(job.trace_path, job.config.get("pricing"))})

    def _handle_run_stop(self, path: str) -> None:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 4:
            self._json({"error": "missing run id"}, status=HTTPStatus.BAD_REQUEST)
            return
        job = STATE.get(parts[2])
        if job is None:
            self._json({"error": "run not found"}, status=HTTPStatus.NOT_FOUND)
            return
        job.stop_event.set()
        if job.status in {"queued", "running"}:
            job.status = "stopping"
        self._json({"run": job.public()})

    def _serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        target = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self._json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> JsonDict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        payload = self.rfile.read(length).decode("utf-8")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _json(self, value: JsonDict, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _run_job(job: DashboardJob) -> None:
    job.status = "running"
    try:
        harness = _make_harness(job.config)
        runner = AgentRunner(
            AgentRunConfig(
                harness=str(job.config["harness"]),
                max_steps=int(job.config["max_steps"]),
                execute=bool(job.config["execute"]),
                base_url=str(job.config["base_url"]),
                timeout=float(job.config["bridge_timeout"]),
                trace_dir=Path(job.config["trace_dir"]),
                memory_path=Path(job.config["memory_path"]),
                start_run=bool(job.config["start_run"]),
                character=str(job.config["character"]),
                ascension=int(job.config["ascension"]),
                stop_on_error=True,
                step_delay=float(job.config["step_delay"]),
                stop_requested=job.stop_event.is_set,
                strategy=job.config.get("strategy"),
                encounter_notes_path=Path(job.config["encounter_notes_path"]) if job.config.get("encounter_notes_path") else None,
            ),
            harness,
        )
        job.trace_path = str(runner.trace.path)
        job.result = runner.run()
        if job.status == "stopping" or job.stop_event.is_set():
            job.status = "stopped"
        else:
            job.status = "completed"
    except Exception as exc:
        job.error = str(exc)
        job.traceback_text = traceback.format_exc()
        job.status = "failed"
    finally:
        job.finished_at = time.time()


def _normalize_run_config(body: JsonDict) -> JsonDict:
    pricing = body.get("pricing") if isinstance(body.get("pricing"), dict) else {}
    harness = str(body.get("harness") or "codex-cli")
    if harness not in {"codex-cli", "claude-code", "cursor-cli"}:
        harness = "codex-cli"
    default_model = HARNESS_DEFAULT_MODELS[harness]
    default_pricing = HARNESS_DEFAULT_PRICING[harness]
    return {
        "harness": harness,
        "codex_bin": body.get("codex_bin") or shutil.which("codex") or "codex",
        "claude_bin": body.get("claude_bin") or shutil.which("claude") or "claude",
        "cursor_bin": body.get("cursor_bin") or shutil.which("cursor-agent") or "cursor-agent",
        "model": body.get("model") or default_model,
        "reasoning_effort": body.get("reasoning_effort") or "medium",
        "agent_workdir": body.get("agent_workdir") or str(ROOT / "agent_profiles/codex_base"),
        "sandbox": body.get("sandbox") or "read-only",
        "approval_policy": body.get("approval_policy") or "never",
        "agent_timeout": int(body.get("agent_timeout") or 180),
        "allow_tools": bool(body.get("allow_tools", False)),
        "web_search": bool(body.get("web_search", False)),
        "max_steps": max(1, min(int(body.get("max_steps") or 500), 500)),
        "execute": bool(body.get("execute", True)),
        "base_url": body.get("base_url") or "http://localhost:15526",
        "bridge_timeout": float(body.get("bridge_timeout") or 10.0),
        "trace_dir": body.get("trace_dir") or str(ROOT / "agent_runs"),
        "memory_path": body.get("memory_path") or str(ROOT / "agent_runs/live-run-memory.json"),
        "encounter_notes_path": body.get("encounter_notes_path")
        or str(Path(body.get("agent_workdir") or str(ROOT / "agent_profiles/codex_base")) / "ENCOUNTERS.md"),
        "start_run": bool(body.get("start_run", True)),
        "character": body.get("character") or "IRONCLAD",
        "ascension": int(body.get("ascension") or 0),
        "step_delay": float(body.get("step_delay") or 0.2),
        "strategy": _normalize_strategy(body.get("strategy") if isinstance(body.get("strategy"), dict) else body),
        "pricing": {
            "input_per_million": _optional_float(pricing.get("input_per_million"), default=default_pricing["input"]),
            "cached_input_per_million": _optional_float(pricing.get("cached_input_per_million"), default=default_pricing["cached"]),
            "output_per_million": _optional_float(pricing.get("output_per_million"), default=default_pricing["output"]),
        },
    }


def _resolve_profile_dir(value: str) -> Path:
    raw = Path(value)
    profile_dir = raw if raw.is_absolute() else ROOT / raw
    profile_dir = profile_dir.resolve()
    profiles_root = (ROOT / "agent_profiles").resolve()
    try:
        profile_dir.relative_to(profiles_root)
    except ValueError as exc:
        raise ValueError("profile must live under agent_profiles") from exc
    if not profile_dir.is_dir():
        raise ValueError("profile directory does not exist")
    return profile_dir


def _profile_label(name: str) -> str:
    words = name.replace("-", " ").replace("_", " ").split()
    return " ".join(word[:1].upper() + word[1:] for word in words) if words else name


def _make_harness(config: JsonDict) -> CodexCliHarness | ClaudeCodeHarness | CursorCliHarness:
    harness = str(config.get("harness") or "codex-cli")
    if harness == "claude-code":
        return ClaudeCodeHarness(
            claude_bin=str(config["claude_bin"]),
            model=config.get("model") or "sonnet",
            reasoning_effort=config.get("reasoning_effort") or "medium",
            agent_workdir=Path(config["agent_workdir"]),
            schema_path=ROOT / "agent_harness/action.schema.json",
            timeout_seconds=int(config["agent_timeout"]),
            allow_tools=bool(config["allow_tools"]),
        )
    if harness == "cursor-cli":
        return CursorCliHarness(
            cursor_bin=str(config["cursor_bin"]),
            model=config.get("model") or "gpt-5",
            agent_workdir=Path(config["agent_workdir"]),
            timeout_seconds=int(config["agent_timeout"]),
            allow_tools=bool(config["allow_tools"]),
        )
    return CodexCliHarness(
        codex_bin=str(config["codex_bin"]),
        model=config.get("model") or None,
        reasoning_effort=config.get("reasoning_effort") or None,
        agent_workdir=Path(config["agent_workdir"]),
        schema_path=ROOT / "agent_harness/action.schema.json",
        sandbox=str(config["sandbox"]),
        approval_policy=str(config["approval_policy"]),
        timeout_seconds=int(config["agent_timeout"]),
        allow_tools=bool(config["allow_tools"]),
        web_search=bool(config["web_search"]),
    )


def _read_trace_events(trace_path: str | None, *, offset: int, pricing: Any) -> JsonDict:
    if not trace_path:
        return {"offset": 0, "events": [], "summary": _empty_summary(pricing)}
    path = Path(trace_path)
    if not path.exists():
        return {"offset": 0, "events": [], "summary": _empty_summary(pricing)}
    size = path.stat().st_size
    if offset < 0 or offset > size:
        offset = 0
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
        next_offset = handle.tell()
    text = data.decode("utf-8", errors="replace")
    events = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return {
        "offset": next_offset,
        "events": events,
        "summary": _summarize_trace(trace_path, pricing),
    }


def _normalize_strategy(body: JsonDict) -> JsonDict:
    risk = str(body.get("risk") or "balanced")
    map_priority = str(body.get("map_priority") or "balanced")
    potion_policy = str(body.get("potion_policy") or "proactive")
    return {
        "risk": risk if risk in {"safe", "balanced", "aggressive"} else "balanced",
        "map_priority": map_priority if map_priority in {"safe", "balanced", "shop", "elite"} else "balanced",
        "potion_policy": potion_policy if potion_policy in {"conserve", "normal", "proactive"} else "proactive",
    }


def _summarize_trace(trace_path: str | None, pricing: Any) -> JsonDict:
    summary = _empty_summary(pricing)
    if not trace_path:
        return summary
    path = Path(trace_path)
    if not path.exists():
        return summary
    last_state: JsonDict | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        summary["events"] += 1
        event_type = event.get("event")
        if event_type == "agent_decision":
            summary["decisions"] += 1
            decision = event.get("decision") if isinstance(event.get("decision"), dict) else {}
            summary["latency_ms"] += int(decision.get("latency_ms") or 0)
            _add_usage(summary["usage"], decision.get("usage"))
            summary["last_action"] = decision.get("action")
            summary["last_rationale"] = decision.get("rationale")
        elif event_type == "action_result":
            summary["actions"] += 1
            state = event.get("state")
            if isinstance(state, dict):
                last_state = state
        elif event_type == "state":
            state = event.get("state")
            if isinstance(state, dict):
                last_state = state
        elif event_type == "memory":
            memory = event.get("memory")
            if isinstance(memory, dict):
                summary["memory"] = memory
        elif event_type in {"bridge_error", "agent_error", "wait_limit"}:
            summary["errors"] += 1
    summary["last_state"] = compact_state_for_agent(last_state) if isinstance(last_state, dict) else None
    summary["cost_estimate_usd"] = _estimate_cost(summary["usage"], pricing)
    return summary


def _empty_summary(pricing: Any) -> JsonDict:
    return {
        "events": 0,
        "decisions": 0,
        "actions": 0,
        "errors": 0,
        "latency_ms": 0,
        "usage": {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
        },
        "cost_estimate_usd": _estimate_cost({}, pricing),
        "last_action": None,
        "last_rationale": None,
        "last_state": None,
        "memory": None,
    }


def _add_usage(total: JsonDict, usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
        total[key] = int(total.get(key) or 0) + int(usage.get(key) or 0)


def _estimate_cost(usage: JsonDict, pricing: Any) -> float | None:
    if not isinstance(pricing, dict):
        return None
    input_rate = pricing.get("input_per_million")
    cached_rate = pricing.get("cached_input_per_million")
    output_rate = pricing.get("output_per_million")
    if input_rate is None and cached_rate is None and output_rate is None:
        return None
    input_tokens = int(usage.get("input_tokens") or 0)
    cached_tokens = int(usage.get("cached_input_tokens") or 0)
    billable_input = max(0, input_tokens - cached_tokens)
    cost = 0.0
    if input_rate is not None:
        cost += billable_input * float(input_rate) / 1_000_000
    if cached_rate is not None:
        cost += cached_tokens * float(cached_rate) / 1_000_000
    if output_rate is not None:
        cost += int(usage.get("output_tokens") or 0) * float(output_rate) / 1_000_000
    return round(cost, 6)


def _optional_float(value: Any, *, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
