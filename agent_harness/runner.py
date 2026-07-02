from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from live_bridge import BridgeApiError, LiveSts2Client

from .codex_cli import CodexCliHarness, HarnessError
from .encounters import load_encounter_notes, select_encounter_notes
from .memory import RunMemory
from .state_prompt import compact_state_for_agent
from .trace import TraceWriter

JsonDict = dict[str, Any]


@dataclass
class AgentRunConfig:
    harness: str = "codex-cli"
    max_steps: int = 1
    execute: bool = False
    base_url: str = "http://localhost:15526"
    timeout: float = 10.0
    trace_dir: Path = Path("agent_runs")
    start_run: bool = False
    character: str = "IRONCLAD"
    ascension: int = 0
    stop_on_error: bool = True
    step_delay: float = 0.2
    stop_requested: Callable[[], bool] | None = None
    memory_path: Path | None = None
    strategy: JsonDict | None = None
    encounter_notes_path: Path | None = None


class AgentRunner:
    def __init__(self, config: AgentRunConfig, agent: CodexCliHarness):
        self.config = config
        self.agent = agent
        self.client = LiveSts2Client(base_url=config.base_url, timeout=config.timeout)
        self.trace = TraceWriter(config.trace_dir, harness_name=config.harness)
        self.memory_path = config.memory_path or (config.trace_dir / "live-run-memory.json")
        self.memory = RunMemory() if config.start_run else RunMemory.load(self.memory_path)
        self.encounter_notes_path = config.encounter_notes_path or (agent.agent_workdir / "ENCOUNTERS.md")
        self.encounter_notes = load_encounter_notes(self.encounter_notes_path)

    def run(self) -> JsonDict:
        if self.config.start_run:
            start_state = self.client.send({
                "cmd": "start_run",
                "character": self.config.character,
                "ascension": self.config.ascension,
            })
            self.memory.observe_state(start_state)
            self.memory.save(self.memory_path)
            self.trace.write({"event": "start_run", "state": compact_state_for_agent(start_state)})
            self.trace.write({"event": "memory", "step": 0, "memory": self.memory.for_prompt()})

        final_state: JsonDict = {}
        steps_to_run = self.config.max_steps
        if not self.config.execute and steps_to_run > 1:
            steps_to_run = 1

        actions_taken = 0
        waits = 0
        max_waits = max(30, steps_to_run * 5)

        while actions_taken < steps_to_run:
            if self.config.stop_requested and self.config.stop_requested():
                self.trace.write({"event": "runner_stopped", "step": actions_taken})
                break

            state = self.client.state()
            final_state = state
            self.memory.observe_state(state)
            compact = compact_state_for_agent(state)
            self.trace.write({"event": "state", "step": actions_taken, "state": compact})
            if state.get("decision") == "game_over":
                self.memory.save(self.memory_path)
                self.trace.write({"event": "memory", "step": actions_taken, "memory": self.memory.for_prompt()})
                break
            if _is_transitional_state(state):
                waits += 1
                self.trace.write({"event": "state_wait", "step": actions_taken, "waits": waits, "state": compact})
                if _is_empty_disabled_rewards(state) and waits >= 8:
                    self.trace.write({
                        "event": "wait_limit",
                        "step": actions_taken,
                        "waits": waits,
                        "state": compact,
                        "error": "Reward screen has no items and no enabled proceed button",
                    })
                    break
                if waits > max_waits:
                    self.trace.write({
                        "event": "wait_limit",
                        "step": actions_taken,
                        "waits": waits,
                        "state": compact,
                    })
                    break
                if self.config.execute:
                    time.sleep(max(self.config.step_delay, 1.0))
                    continue
                break
            waits = 0

            try:
                decision = self.agent.decide(
                    state,
                    step=actions_taken,
                    run_context={
                        "execute": self.config.execute,
                        "trace_path": str(self.trace.path),
                        "memory": self.memory.for_prompt(),
                        "strategy": self.config.strategy or {},
                        "encounter_knowledge": select_encounter_notes(self.encounter_notes, state),
                    },
                )
            except HarnessError as exc:
                self.trace.write({"event": "agent_error", "step": actions_taken, "error": str(exc)})
                if self.config.stop_on_error:
                    raise
                break

            self.trace.write({
                "event": "agent_decision",
                "step": actions_taken,
                "decision": decision.to_trace(),
                "command_payload": decision.command_payload(),
            })

            if not self.config.execute:
                final_state = state
                break

            if self.config.stop_requested and self.config.stop_requested():
                self.trace.write({"event": "runner_stopped", "step": actions_taken})
                break

            try:
                final_state = self.client.send(decision.command_payload())
                self.memory.record_decision(
                    step=actions_taken,
                    state=state,
                    decision=decision,
                    result_state=final_state,
                )
                self.memory.save(self.memory_path)
                self.trace.write({
                    "event": "action_result",
                    "step": actions_taken,
                    "state": compact_state_for_agent(final_state),
                    "last_action_result": final_state.get("_last_action_result"),
                })
                self.trace.write({"event": "memory", "step": actions_taken, "memory": self.memory.for_prompt()})
            except BridgeApiError as exc:
                self.trace.write({
                    "event": "bridge_error",
                    "step": actions_taken,
                    "error": str(exc),
                    "command_payload": decision.command_payload(),
                })
                final_state = self._recover_bridge_error(state, decision, exc)
                if final_state is not None:
                    self.memory.observe_state(final_state)
                    self.memory.save(self.memory_path)
                    self.trace.write({
                        "event": "action_result",
                        "step": actions_taken,
                        "state": compact_state_for_agent(final_state),
                        "last_action_result": final_state.get("_last_action_result"),
                        "recovery": True,
                        "recovered_from": str(exc),
                    })
                    self.trace.write({"event": "memory", "step": actions_taken, "memory": self.memory.for_prompt()})
                elif self.config.stop_on_error:
                    raise
                else:
                    break
            actions_taken += 1

            if self.config.step_delay:
                time.sleep(self.config.step_delay)

        return {
            "trace_path": str(self.trace.path),
            "execute": self.config.execute,
            "actions_taken": actions_taken,
            "final_state": compact_state_for_agent(final_state) if final_state else {},
            "memory_path": str(self.memory_path),
        }

    def _recover_bridge_error(self, previous_state: JsonDict, decision: Any, exc: BridgeApiError) -> JsonDict | None:
        time.sleep(max(self.config.step_delay, 0.5))
        try:
            state = self.client.state()
        except BridgeApiError:
            return None

        if decision.action == "play_card" and _looks_like_stale_action_error(exc):
            if state.get("decision") == "combat_play" and not _has_playable_cards(state):
                recovered = self.client.send({"cmd": "action", "action": "end_turn"})
                recovered["_last_action_result"] = {
                    "status": "ok",
                    "message": f"Ended turn after stale hand state: {exc}",
                }
                return recovered

        if _is_transitional_state(state):
            state["_last_action_result"] = {
                "status": "ok",
                "message": f"Recovered from bridge error by refreshing into a transitional state: {exc}",
            }
            return state

        if _action_surface_changed(previous_state, state):
            state["_last_action_result"] = {
                "status": "ok",
                "message": f"Recovered from stale action after game state changed: {exc}",
            }
            return state

        return None


def _is_transitional_state(state: JsonDict) -> bool:
    if state.get("decision") == "unknown":
        return True
    if state.get("decision") == "combat_play" and not state.get("is_play_phase", True):
        return True
    if state.get("decision") == "combat_rewards":
        return _is_empty_disabled_rewards(state)
    if state.get("decision") == "event_choice":
        return state.get("options") == [] and not state.get("in_dialogue", False)
    return False


def _is_empty_disabled_rewards(state: JsonDict) -> bool:
    return state.get("decision") == "combat_rewards" and state.get("items") == [] and not state.get("can_proceed", False)


def _has_playable_cards(state: JsonDict) -> bool:
    hand = state.get("hand")
    if not isinstance(hand, list):
        return False
    for card in hand:
        if not isinstance(card, dict):
            continue
        if card.get("can_play") is False or card.get("playable") is False:
            continue
        if card.get("unplayable_reason"):
            continue
        return True
    return False


def _looks_like_stale_action_error(exc: BridgeApiError) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "out of range",
            "hand has",
            "invalid target_index",
            "not available",
            "not open",
            "no longer",
            "already",
        )
    )


def _action_surface_changed(previous_state: JsonDict, state: JsonDict) -> bool:
    return compact_state_for_agent(previous_state) != compact_state_for_agent(state)
