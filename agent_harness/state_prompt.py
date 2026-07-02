from __future__ import annotations

import json
from typing import Any

JsonDict = dict[str, Any]


def build_decision_prompt(
    state: JsonDict,
    *,
    step: int,
    run_context: JsonDict,
    allow_tools: bool,
) -> str:
    compact = compact_state_for_agent(state)
    guide = action_guide(compact)
    persistent_memory = run_context.get("memory") if isinstance(run_context.get("memory"), dict) else None
    strategy = run_context.get("strategy") if isinstance(run_context.get("strategy"), dict) else None
    encounter_knowledge = run_context.get("encounter_knowledge")
    if not isinstance(encounter_knowledge, str):
        encounter_knowledge = ""
    visible_run_context = {
        key: value
        for key, value in run_context.items()
        if key not in {"memory", "strategy", "encounter_knowledge"}
    }
    tool_instruction = (
        "You may use available Codex tools only when they directly improve this one move. "
        "Keep any public notes in tool_notes and still return only the final JSON object."
        if allow_tools
        else "Do not run shell commands or use tools. Decide from the supplied game state only."
    )
    return (
        "You are choosing the next action for a visible Slay the Spire 2 run.\n"
        "Return exactly one JSON object that matches the provided schema. Do not use markdown.\n"
        "Expose only a concise public rationale, not hidden scratch work.\n"
        f"{tool_instruction}\n\n"
        "Action contract:\n"
        "{\n"
        '  "rationale": "short public explanation",\n'
        '  "action": "bridge_action_name",\n'
        '  "args": {"index": null, "card_index": 0, "target_index": 0, "...": null},\n'
        '  "expected": "short expected outcome",\n'
        '  "confidence": 0.0,\n'
        '  "tool_notes": []\n'
        "}\n\n"
        "Use null for every unused args key required by the schema.\n\n"
        "Index rules:\n"
        "- card_index is the zero-based index field from the current hand/cards list.\n"
        "- target_index is the zero-based row position in the enemies list, not combat_id.\n\n"
        "Available action guide for the current decision:\n"
        f"{guide}\n\n"
        "Strategic defaults:\n"
        "- In combat, prefer lethal damage, then prevent incoming damage, then improve future turns.\n"
        "- Before claiming a lethal line, add the energy costs of every card in the line and confirm all cards remain playable after each prior play.\n"
        "- Do not describe a future card sequence as available if current energy cannot pay for the sequence.\n"
        "- Treat the displayed card damage and enemy HP as hard constraints. If a card says 8 damage and the enemy has 10 HP, that card is not lethal.\n"
        "- When no lethal exists this turn, preserve HP with block after useful damage instead of pretending a near-lethal attack ends the fight.\n"
        "- Potions are survival tools, not trophies. Use them in elites, bosses, lethal-risk turns, or when they convert a bad turn into a safe or winning turn.\n"
        "- If potion slots are full, be more willing to use a potion so future potion rewards are not wasted.\n"
        "- From Act 2 onward, if HP is below about 75% or incoming damage will exceed block by 10+, use defensive sustain potions proactively unless you have lethal this turn.\n"
        "- Use long-duration potions early enough to matter: Regen before/after the first real hit, Dexterity before playing block cards in fights that will last several turns.\n"
        "- On the map, prefer paths with useful rewards while managing HP risk. With high gold, strongly prefer visiting shops.\n"
        "- At shops, spend gold on strong relics/cards/removal instead of hoarding it.\n"
        "- For rewards, improve deck quality over taking every card.\n"
        "- If no productive combat action remains, end the turn.\n\n"
        "Encounter-specific knowledge:\n"
        "If this section applies to the current enemy or status mechanic, it overrides generic risk heuristics.\n"
        f"{encounter_knowledge or 'No curated encounter note matched this state.'}\n\n"
        "Player strategy config:\n"
        f"{json.dumps(strategy or {}, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "Persistent run memory:\n"
        f"{json.dumps(persistent_memory or {}, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        f"Runner step: {step}\n"
        f"Run context: {json.dumps(visible_run_context, ensure_ascii=False, sort_keys=True)}\n\n"
        "Current normalized game state:\n"
        f"{json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True)}\n"
    )


def compact_state_for_agent(state: JsonDict) -> JsonDict:
    """Keep the agent prompt focused while preserving legal indices."""
    decision = state.get("decision")
    compact: JsonDict = {
        "decision": decision,
        "type": state.get("type"),
        "context": state.get("context"),
        "run": _pick(state.get("run"), ["act", "floor", "ascension", "seed", "character"]),
    }
    for key in (
        "room_type",
        "round",
        "turn",
        "is_play_phase",
        "energy",
        "max_energy",
        "can_proceed",
        "can_skip",
        "can_confirm",
        "can_cancel",
        "screen_type",
        "prompt",
        "event_name",
        "event_id",
        "description",
        "message",
        "in_dialogue",
        "required_count",
        "selection_intent",
        "selection_hint",
        "is_ancient",
        "raw_state_type",
    ):
        if key in state:
            compact[key] = state.get(key)

    player = state.get("player")
    if isinstance(player, dict):
        compact["player"] = _pick(
            player,
            [
                "name",
                "hp",
                "max_hp",
                "block",
                "gold",
                "potion_slots",
                "open_potion_slots",
                "energy",
                "max_energy",
                "deck_count",
                "draw_pile_count",
                "discard_pile_count",
                "exhaust_pile_count",
                "relics",
                "potions",
                "powers",
            ],
        )
    for key in ("hand", "enemies", "choices", "options", "items", "cards", "relics", "potions"):
        value = state.get(key)
        if isinstance(value, list):
            compact[key] = [_compact_row(item, key) for item in value]
    if "map" in state and "nodes" in state:
        compact["map_hint"] = "Full map omitted from prompt; choose only from choices by index."
    return _limit_json(compact)


def action_guide(state: JsonDict) -> str:
    decision = state.get("decision")
    if decision == "menu":
        return (
            '- continue_game with args {} if a run is available.\n'
            '- start_new_game with args {"character":"IRONCLAD","ascension":0} to start fresh.'
        )
    if decision == "map_select":
        return (
            '- select_map_node with args {"index": <choice index from choices>}.\n'
            '- Use each choice.path_preview to avoid forced combat chains and route toward rest/shop/elite goals.\n'
            '- Prefer a Shop choice when player.gold is high, especially above 250.\n'
            '- At low HP, prefer the path with the nearest RestSite and fewest monsters_before_rest.'
        )
    if decision == "combat_play":
        if state.get("is_play_phase") is False:
            return '- wait with args {"seconds": 1} until the player play phase begins.'
        return (
            '- play_card with args {"card_index": <hand index>, "target_index": <zero-based enemies row>} for targeted cards.\n'
            '- play_card with args {"card_index": <hand index>} for non-targeted cards.\n'
            '- use_potion with args {"slot": <potion slot>, "target_index": <zero-based enemies row>} for targeted potions.\n'
            '- use_potion with args {"slot": <potion slot>} for self/no-target potions when the potion materially improves survival, damage, or this fight.\n'
            '- If hand is empty or every card has can_play false, use end_turn unless a potion clearly solves the turn.\n'
            '- With full potion slots in Act 2+, prefer using Regen/Dexterity before taking large chip damage; potions cost no energy.\n'
            '- end_turn with args {} when done.'
        )
    if decision == "event_choice":
        return (
            '- choose_event_option with args {"index": <option index>}.\n'
            '- advance_dialogue with args {} only when in_dialogue is true.\n'
            '- wait with args {"seconds": 1} if no options are visible and in_dialogue is false.'
        )
    if decision == "rest_site":
        return '- choose_rest_option with args {"index": <option index>} or proceed with args {} if can_proceed is true.'
    if decision == "shop":
        return (
            '- shop_purchase with args {"index": <item index>} for valuable relics, cards, potions with empty slots, or card removal.\n'
            '- With high gold, buy useful upgrades before proceeding; do not leave with large unused gold unless the shop is bad.'
        )
    if decision == "combat_rewards":
        return (
            '- If items is non-empty, claim_reward with args {"index": <item index>}.\n'
            '- If a potion reward is visible but player.open_potion_slots is 0, do not claim that potion; claim another reward or proceed when appropriate.\n'
            '- Do not proceed while reward items remain.\n'
            '- proceed with args {} only when items is empty and can_proceed is true.\n'
            '- wait with args {"seconds": 1} when items is empty and can_proceed is false.'
        )
    if decision == "card_reward":
        return '- select_card_reward with args {"card_index": <card index>} or skip_card_reward with args {}.'
    if decision == "card_select":
        lines = []
        if state.get("selection_hint"):
            lines.append(f'- Selection context: {state.get("selection_hint")}')
        if state.get("required_count"):
            lines.append(
                '- For multi-card prompts, prefer one batch action: '
                'select_cards with args {"indices":"<comma-separated card indices>"} using exactly required_count cards.'
            )
            lines.append("- Do not repeat select_card on the same index; card selection toggles on/off.")
        lines.extend(
            [
                '- select_card with args {"index": <card index>} for single-card selection or one deliberate toggle.',
                '- confirm_selection with args {} when can_confirm is true.',
                '- cancel_selection with args {} when can_cancel is true.',
            ]
        )
        return "\n".join(lines)
    if decision == "hand_select":
        if state.get("can_confirm"):
            return (
                '- combat_confirm_selection with args {} now; a card is already selected and ready to confirm.\n'
                '- Do not select another card while can_confirm is true unless you intentionally need to change the selection.'
            )
        return (
            '- combat_select_card with args {"card_index": <card index>}.\n'
            '- cancel_selection with args {} if available.'
        )
    if decision == "relic_select":
        return '- select_relic with args {"index": <relic index>} or skip_relic_selection with args {}.'
    if decision == "treasure":
        return (
            '- claim_treasure_relic with args {"index": <relic index>} only when relics is non-empty.\n'
            '- proceed with args {} when relics is empty and can_proceed is true.'
        )
    if decision == "game_over":
        return '- return_to_main_menu with args {}.'
    if decision in {"unknown", "overlay"}:
        return '- wait with args {"seconds": 1} while the visible game finishes changing screens.'
    return '- Choose the most specific bridge action supported by live_bridge for this decision.'


def _compact_row(item: Any, collection: str) -> Any:
    if not isinstance(item, dict):
        return item
    if collection == "choices":
        return _compact_choice(item)
    keys_by_collection = {
        "hand": [
            "index",
            "name",
            "id",
            "cost",
            "star_cost",
            "type",
            "rarity",
            "damage",
            "block",
            "magic_number",
            "description",
            "upgraded",
            "is_upgraded",
            "playable",
            "can_play",
            "unplayable_reason",
            "target_required",
            "target_type",
            "keywords",
        ],
        "enemies": [
            "index",
            "name",
            "id",
            "entity_id",
            "combat_id",
            "hp",
            "max_hp",
            "block",
            "intent",
            "intent_damage",
            "intent_hits",
            "intents",
            "status",
            "powers",
        ],
        "options": [
            "index",
            "title",
            "label",
            "text",
            "description",
            "is_locked",
            "disabled",
            "enabled",
            "is_proceed",
            "was_chosen",
            "keywords",
        ],
        "items": ["index", "category", "name", "price", "description", "can_afford", "sold_out"],
        "cards": ["index", "card_index", "name", "id", "cost", "type", "rarity", "description", "upgraded"],
        "relics": ["index", "name", "id", "description"],
        "potions": ["slot", "index", "name", "id", "description"],
    }
    return _pick(item, keys_by_collection.get(collection, list(item.keys())))


def _compact_choice(item: JsonDict) -> JsonDict:
    result = _pick(item, ["index", "col", "row", "type", "children", "name", "description"])
    preview = item.get("path_preview")
    if isinstance(preview, dict):
        result["path_preview"] = _pick(
            preview,
            ["nearest_shop", "nearest_rest", "nearest_elite", "monsters_before_rest", "forced_nodes", "reachable_counts"],
        )
    return result


def _pick(value: Any, keys: list[str]) -> JsonDict:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in keys if key in value}


def _limit_json(value: Any, *, max_string: int = 900, max_items: int = 60, depth: int = 0) -> Any:
    if depth > 6:
        return "..."
    if isinstance(value, str):
        return value if len(value) <= max_string else value[:max_string] + "..."
    if isinstance(value, list):
        limited = value[:max_items]
        result = [_limit_json(item, max_string=max_string, max_items=max_items, depth=depth + 1) for item in limited]
        if len(value) > max_items:
            result.append({"omitted_items": len(value) - max_items})
        return result
    if isinstance(value, dict):
        return {
            str(key): _limit_json(item, max_string=max_string, max_items=max_items, depth=depth + 1)
            for key, item in value.items()
        }
    return value
