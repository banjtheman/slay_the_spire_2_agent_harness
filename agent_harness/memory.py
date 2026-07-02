from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .codex_cli import AgentDecision

JsonDict = dict[str, Any]


@dataclass
class RunMemory:
    """Deterministic per-run memory fed back into each agent decision."""

    run_summary: JsonDict = field(default_factory=dict)
    build_plan: JsonDict = field(default_factory=lambda: {
        "archetype": "unknown",
        "priorities": [],
        "avoid": [],
    })
    map_plan: JsonDict = field(default_factory=dict)
    resource_plan: JsonDict = field(default_factory=dict)
    notable_events: list[str] = field(default_factory=list)
    recent_decisions: list[JsonDict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "RunMemory":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        memory = cls()
        memory.run_summary = _dict(data.get("run_summary"))
        memory.build_plan = _dict(data.get("build_plan")) or memory.build_plan
        memory.map_plan = _dict(data.get("map_plan"))
        memory.resource_plan = _dict(data.get("resource_plan"))
        memory.notable_events = _string_list(data.get("notable_events"))[-16:]
        memory.recent_decisions = _dict_list(data.get("recent_decisions"))[-12:]
        return memory

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.for_prompt(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def observe_state(self, state: JsonDict) -> None:
        context = state.get("context") if isinstance(state.get("context"), dict) else {}
        player = state.get("player") if isinstance(state.get("player"), dict) else {}
        previous = self.run_summary
        effective_player = dict(player)
        for key in ("hp", "max_hp", "gold"):
            if effective_player.get(key) is None and previous.get(key) is not None:
                effective_player[key] = previous.get(key)
        self.run_summary = {
            "act": context.get("act"),
            "floor": context.get("floor"),
            "ascension": context.get("ascension"),
            "decision": state.get("decision"),
            "hp": effective_player.get("hp"),
            "max_hp": effective_player.get("max_hp"),
            "gold": effective_player.get("gold"),
        }
        if player or not self.resource_plan:
            self.resource_plan = _resource_plan(effective_player, context)
        self.build_plan = _merge_build_plan(self.build_plan, _build_plan(effective_player, state))
        if state.get("decision") == "map_select":
            self.map_plan = _map_plan(state, player)

    def record_decision(
        self,
        *,
        step: int,
        state: JsonDict,
        decision: AgentDecision,
        result_state: JsonDict | None,
    ) -> None:
        context = state.get("context") if isinstance(state.get("context"), dict) else {}
        player = state.get("player") if isinstance(state.get("player"), dict) else {}
        row: JsonDict = {
            "step": step,
            "floor": context.get("floor"),
            "decision": state.get("decision"),
            "action": decision.action,
            "args": decision.args,
            "rationale": decision.rationale,
            "hp": player.get("hp"),
            "gold": player.get("gold"),
        }
        if state.get("decision") == "map_select":
            choice = _choice_by_index(state.get("choices"), decision.args.get("index"))
            if choice:
                row["map_choice"] = {
                    "type": choice.get("type"),
                    "path_preview": choice.get("path_preview"),
                }
        self.recent_decisions.append(row)
        self.recent_decisions = self.recent_decisions[-12:]
        if result_state:
            self.observe_state(result_state)
        self._add_notable_event(row, state, result_state)

    def for_prompt(self) -> JsonDict:
        return {
            "run_summary": self.run_summary,
            "build_plan": self.build_plan,
            "map_plan": self.map_plan,
            "resource_plan": self.resource_plan,
            "notable_events": self.notable_events[-8:],
            "recent_decisions": self.recent_decisions[-8:],
        }

    def _add_notable_event(self, row: JsonDict, state: JsonDict, result_state: JsonDict | None) -> None:
        decision = state.get("decision")
        action = row.get("action")
        if action == "use_potion":
            self._note(f"Used potion {row.get('args')} on floor {row.get('floor')}: {row.get('rationale')}")
        elif decision == "map_select" and "map_choice" in row:
            preview = row["map_choice"].get("path_preview") if isinstance(row.get("map_choice"), dict) else None
            self._note(f"Chose map node {row['map_choice'].get('type')} on floor {row.get('floor')} with preview {preview}")
        elif decision == "card_reward" and action == "select_card_reward":
            self._note(f"Took card reward on floor {row.get('floor')}: {row.get('rationale')}")
        elif decision == "shop" and action == "shop_purchase":
            self._note(f"Bought shop item {row.get('args')} on floor {row.get('floor')}: {row.get('rationale')}")
        if result_state and result_state.get("decision") == "game_over":
            self._note(f"Run ended on floor {row.get('floor')} after action {action}.")

    def _note(self, text: str) -> None:
        if not text:
            return
        self.notable_events.append(text)
        self.notable_events = self.notable_events[-16:]


def _resource_plan(player: JsonDict, context: JsonDict) -> JsonDict:
    hp = _number(player.get("hp"))
    max_hp = _number(player.get("max_hp"))
    hp_ratio = hp / max_hp if hp is not None and max_hp else None
    gold = _number(player.get("gold"))
    potions = player.get("potions") if isinstance(player.get("potions"), list) else []
    plan: JsonDict = {
        "hp_ratio": round(hp_ratio, 2) if hp_ratio is not None else None,
        "gold": gold,
        "potion_count": len(potions),
        "potion_names": [_name(item) for item in potions],
        "stance": "normal",
    }
    if hp_ratio is not None and hp_ratio <= 0.35:
        plan["stance"] = "survive_to_rest"
        plan["guidance"] = "Avoid optional elites; spend potions early; rest over upgrade unless lethal risk is gone."
    elif gold is not None and gold >= 250:
        plan["stance"] = "convert_gold"
        plan["guidance"] = "Prefer shops and buy power now; unspent gold is not helping the run."
    if int(context.get("act") or 0) >= 2 and potions:
        plan["potion_guidance"] = "Use relevant potions before large chip damage; do not wait for perfect lethal."
    return plan


def _build_plan(player: JsonDict, state: JsonDict) -> JsonDict:
    relics = player.get("relics") if isinstance(player.get("relics"), list) else []
    cards = state.get("cards") if isinstance(state.get("cards"), list) else []
    hand = state.get("hand") if isinstance(state.get("hand"), list) else []
    all_cards = cards + hand
    names = [_name(card) for card in all_cards]
    priorities: list[str] = []
    avoid: list[str] = []
    if any("Strength" in str(card.get("description", "")) for card in all_cards if isinstance(card, dict)):
        priorities.append("strength-scaling attacks and multi-hit cards")
    if any(name in {"Shrug It Off", "Pommel Strike", "Thunderclap"} for name in names):
        priorities.append("efficient draw/vulnerable/block cards")
    if any(_name(relic) == "Pael's Tooth" for relic in relics):
        priorities.append("choose high-impact Pael's Tooth upgrade targets")
        avoid.append("treating Pael's Tooth as normal permanent removal")
    return {
        "archetype": "ironclad_midrange",
        "priorities": priorities[:5],
        "avoid": avoid[:5],
    }


def _merge_build_plan(previous: JsonDict, current: JsonDict) -> JsonDict:
    archetype = current.get("archetype") or previous.get("archetype") or "unknown"
    priorities = _merge_text_list(previous.get("priorities"), current.get("priorities"))
    avoid = _merge_text_list(previous.get("avoid"), current.get("avoid"))
    return {
        "archetype": archetype,
        "priorities": priorities[:5],
        "avoid": avoid[:5],
    }


def _merge_text_list(*values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            key = item.lower()
            if key not in seen:
                result.append(item)
                seen.add(key)
    return result


def _map_plan(state: JsonDict, player: JsonDict) -> JsonDict:
    choices = state.get("choices") if isinstance(state.get("choices"), list) else []
    hp = _number(player.get("hp"))
    max_hp = _number(player.get("max_hp"))
    hp_ratio = hp / max_hp if hp is not None and max_hp else None
    gold = _number(player.get("gold")) or 0
    rows = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        preview = choice.get("path_preview") if isinstance(choice.get("path_preview"), dict) else {}
        rows.append({
            "index": choice.get("index"),
            "type": choice.get("type"),
            "nearest_shop": preview.get("nearest_shop"),
            "nearest_rest": preview.get("nearest_rest"),
            "monsters_before_rest": preview.get("monsters_before_rest"),
            "forced_nodes": preview.get("forced_nodes"),
        })
    guidance = "Pick the highest-value path."
    if hp_ratio is not None and hp_ratio <= 0.35:
        guidance = "Low HP: prioritize nearest rest and avoid forced monster chains."
    elif gold >= 250:
        guidance = "High gold: prefer a path with a reachable shop before more elites/forced fights."
    return {"guidance": guidance, "choices": rows}


def _choice_by_index(choices: Any, index: Any) -> JsonDict | None:
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if isinstance(choice, dict) and choice.get("index") == index:
            return choice
    return None


def _name(value: Any) -> str:
    return str(value.get("name") or value.get("potion_name") or "") if isinstance(value, dict) else ""


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict(value: Any) -> JsonDict:
    return dict(value) if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[JsonDict]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []
