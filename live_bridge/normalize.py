from __future__ import annotations

import re
from typing import Any

JsonDict = dict[str, Any]


def normalize_state(raw_state: JsonDict) -> JsonDict:
    """Normalize STS2_Bridge raw state into a headless-like decision shape."""
    state_type = str(raw_state.get("state_type") or "unknown")
    run = _copy_dict(raw_state.get("run"))
    context = {
        "act": run.get("act"),
        "floor": run.get("floor"),
        "ascension": run.get("ascension"),
    }

    if state_type in {"monster", "elite", "boss"}:
        battle = _copy_dict(raw_state.get("battle"))
        player = _copy_dict(battle.get("player"))
        return {
            "type": "decision",
            "decision": "combat_play",
            "room_type": state_type,
            "context": context,
            "run": run,
            "round": battle.get("round"),
            "turn": battle.get("turn"),
            "is_play_phase": battle.get("is_play_phase"),
            "energy": player.get("energy", 0),
            "max_energy": player.get("max_energy", 0),
            "hand": _copy_list(player.get("hand")),
            "enemies": _copy_list(battle.get("enemies")),
            "player": player,
            "draw_pile_count": player.get("draw_pile_count", 0),
            "discard_pile_count": player.get("discard_pile_count", 0),
            "exhaust_pile_count": player.get("exhaust_pile_count", 0),
            "battle": battle,
        }

    if state_type == "hand_select":
        hand_select = _copy_dict(raw_state.get("hand_select"))
        battle = _copy_dict(raw_state.get("battle"))
        return {
            "type": "decision",
            "decision": "hand_select",
            "context": context,
            "run": run,
            "mode": hand_select.get("mode"),
            "prompt": hand_select.get("prompt"),
            "cards": _copy_list(hand_select.get("cards")),
            "selected_cards": _copy_list(hand_select.get("selected_cards")),
            "can_confirm": hand_select.get("can_confirm", False),
            "player": _copy_dict(battle.get("player")),
            "battle": battle,
            "hand_select": hand_select,
        }

    if state_type == "map":
        map_state = _copy_dict(raw_state.get("map"))
        nodes = _copy_list(map_state.get("nodes"))
        choices = _copy_list(map_state.get("next_options"))
        if not choices:
            choices = _starting_map_choices(nodes)
        choices = _annotate_map_choices(choices, nodes)
        return {
            "type": "decision",
            "decision": "map_select",
            "context": context,
            "run": run,
            "choices": choices,
            "player": _copy_dict(map_state.get("player")),
            "current_position": _copy_dict(map_state.get("current_position")),
            "visited": _copy_list(map_state.get("visited")),
            "nodes": nodes,
            "boss": _copy_dict(map_state.get("boss")),
            "map": map_state,
        }

    if state_type == "event":
        event = _copy_dict(raw_state.get("event"))
        return {
            "type": "decision",
            "decision": "event_choice",
            "context": context,
            "run": run,
            "event_name": event.get("event_name"),
            "event_id": event.get("event_id"),
            "is_ancient": event.get("is_ancient", False),
            "description": event.get("body"),
            "options": _copy_list(event.get("options")),
            "player": _copy_dict(event.get("player")),
            "in_dialogue": event.get("in_dialogue", False),
            "event": event,
        }

    if state_type == "rest_site":
        rest = _copy_dict(raw_state.get("rest_site"))
        return {
            "type": "decision",
            "decision": "rest_site",
            "context": context,
            "run": run,
            "options": _copy_list(rest.get("options")),
            "player": _copy_dict(rest.get("player")),
            "can_proceed": rest.get("can_proceed", False),
            "rest_site": rest,
        }

    if state_type == "shop":
        shop = _copy_dict(raw_state.get("shop"))
        items = _copy_list(shop.get("items"))
        return {
            "type": "decision",
            "decision": "shop",
            "context": context,
            "run": run,
            "items": items,
            "cards": [item for item in items if item.get("category") == "card"],
            "relics": [item for item in items if item.get("category") == "relic"],
            "potions": [item for item in items if item.get("category") == "potion"],
            "card_removal": next((item for item in items if item.get("category") == "card_removal"), None),
            "player": _copy_dict(shop.get("player")),
            "can_proceed": shop.get("can_proceed", False),
            "shop": shop,
        }

    if state_type == "combat_rewards":
        rewards = _copy_dict(raw_state.get("rewards"))
        return {
            "type": "decision",
            "decision": "combat_rewards",
            "context": context,
            "run": run,
            "items": _copy_list(rewards.get("items")),
            "can_proceed": rewards.get("can_proceed", False),
            "player": _copy_dict(rewards.get("player")),
            "rewards": rewards,
        }

    if state_type == "card_reward":
        reward = _copy_dict(raw_state.get("card_reward"))
        return {
            "type": "decision",
            "decision": "card_reward",
            "context": context,
            "run": run,
            "cards": _copy_list(reward.get("cards")),
            "can_skip": reward.get("can_skip", False),
            "player": _copy_dict(reward.get("player")),
            "card_reward": reward,
        }

    if state_type == "card_select":
        card_select = _copy_dict(raw_state.get("card_select"))
        selection_meta = _card_select_metadata(card_select)
        return {
            "type": "decision",
            "decision": "card_select",
            "context": context,
            "run": run,
            "screen_type": card_select.get("screen_type"),
            "prompt": card_select.get("prompt"),
            "cards": _copy_list(card_select.get("cards")),
            "player": _copy_dict(card_select.get("player")),
            "preview_showing": card_select.get("preview_showing", False),
            "can_skip": card_select.get("can_skip", False),
            "can_confirm": card_select.get("can_confirm", False),
            "can_cancel": card_select.get("can_cancel", False),
            "card_select": card_select,
            **selection_meta,
        }

    if state_type == "relic_select":
        relic_select = _copy_dict(raw_state.get("relic_select"))
        return {
            "type": "decision",
            "decision": "relic_select",
            "context": context,
            "run": run,
            "prompt": relic_select.get("prompt"),
            "relics": _copy_list(relic_select.get("relics")),
            "player": _copy_dict(relic_select.get("player")),
            "can_skip": relic_select.get("can_skip", False),
            "relic_select": relic_select,
        }

    if state_type == "treasure":
        treasure = _copy_dict(raw_state.get("treasure"))
        return {
            "type": "decision",
            "decision": "treasure",
            "context": context,
            "run": run,
            "relics": _copy_list(treasure.get("relics")),
            "player": _copy_dict(treasure.get("player")),
            "can_proceed": treasure.get("can_proceed", False),
            "message": treasure.get("message"),
            "treasure": treasure,
        }

    if state_type == "game_over":
        game_over = _copy_dict(raw_state.get("game_over"))
        return {
            "type": "decision",
            "decision": "game_over",
            "context": context,
            "run": run,
            "player": _copy_dict(game_over.get("player")),
            "screen_type": game_over.get("screen_type"),
            "can_return_to_main_menu": game_over.get("can_return_to_main_menu", False),
            "options": _copy_list(game_over.get("options")),
            "game_over": game_over,
        }

    if state_type == "menu":
        menu = _copy_dict(raw_state.get("menu"))
        return {
            "type": "status",
            "decision": "menu",
            "context": context,
            "run": run,
            "message": raw_state.get("message"),
            "screen": menu.get("screen"),
            "can_continue_game": menu.get("can_continue_game", False),
            "can_start_new_game": menu.get("can_start_new_game", False),
            "can_abandon_game": menu.get("can_abandon_game", False),
            "characters": _copy_list(menu.get("characters")),
            "ascension": menu.get("ascension"),
            "menu": menu,
        }

    return {
        "type": "status",
        "decision": state_type if state_type != "unknown" else "unknown",
        "context": context,
        "run": run,
        "raw_state_type": state_type,
        "message": raw_state.get("message"),
        "raw": raw_state,
    }


def _copy_dict(value: Any) -> JsonDict:
    return dict(value) if isinstance(value, dict) else {}


def _copy_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _card_select_metadata(card_select: JsonDict) -> JsonDict:
    prompt = str(card_select.get("prompt") or "")
    metadata: JsonDict = {}

    count_match = re.search(r"\bchoose\s+(\d+)\s+cards?\b", prompt, flags=re.IGNORECASE)
    if count_match:
        metadata["required_count"] = int(count_match.group(1))

    remove_match = re.search(r"\bchoose\s+\d+\s+cards?\s+to\s+remove\b", prompt, flags=re.IGNORECASE)
    if remove_match:
        metadata["selection_intent"] = "temporary_remove_for_upgrade"
        metadata["selection_hint"] = (
            "This matches the Pale Tooth relic flow: choose cards to remove temporarily; "
            "they return upgraded after each battle. Treat this as selecting upgrade targets, "
            "not permanent card removal. Prefer high-impact cards with valuable upgrades over basic junk."
        )

    return metadata


def _starting_map_choices(nodes: list[Any]) -> list[JsonDict]:
    """Bridge sometimes omits next_options before the first map click."""
    starts = [node for node in nodes if isinstance(node, dict) and node.get("row") == 0]
    starts.sort(key=lambda node: int(node.get("col", 0)))
    choices: list[JsonDict] = []
    for index, node in enumerate(starts):
        choices.append({
            "index": index,
            "col": node.get("col"),
            "row": node.get("row"),
            "type": node.get("type"),
            "children": _copy_list(node.get("children")),
        })
    return choices


def _annotate_map_choices(choices: list[Any], nodes: list[Any]) -> list[Any]:
    graph = _map_graph(nodes)
    if not graph:
        return choices
    annotated: list[Any] = []
    for choice in choices:
        if not isinstance(choice, dict):
            annotated.append(choice)
            continue
        enriched = dict(choice)
        coordinate = choice.get("coordinate") if isinstance(choice.get("coordinate"), dict) else choice
        key = _node_key(coordinate)
        if key is not None:
            enriched["path_preview"] = _path_preview(key, graph)
        annotated.append(enriched)
    return annotated


def _map_graph(nodes: list[Any]) -> dict[tuple[int, int], JsonDict]:
    graph: dict[tuple[int, int], JsonDict] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        key = _node_key(node)
        if key is None:
            continue
        graph[key] = node
    return graph


def _node_key(node: JsonDict) -> tuple[int, int] | None:
    try:
        return (int(node["col"]), int(node["row"]))
    except (KeyError, TypeError, ValueError):
        return None


def _path_preview(start: tuple[int, int], graph: dict[tuple[int, int], JsonDict], *, max_depth: int = 12) -> JsonDict:
    queue: list[tuple[tuple[int, int], int, int, bool]] = [(start, 0, 0, False)]
    seen: set[tuple[tuple[int, int], int]] = set()
    counts: dict[str, int] = {}
    min_distance: dict[str, int] = {}
    min_monsters_before_rest: int | None = None

    while queue:
        key, distance, monsters_seen, passed_rest = queue.pop(0)
        if (key, distance) in seen or distance > max_depth:
            continue
        seen.add((key, distance))
        node = graph.get(key)
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "Unknown")
        counts[node_type] = counts.get(node_type, 0) + 1
        min_distance.setdefault(node_type, distance)
        next_monsters = monsters_seen + (1 if node_type == "Monster" else 0)
        next_passed_rest = passed_rest or node_type == "RestSite"
        if node_type == "RestSite" and min_monsters_before_rest is None:
            min_monsters_before_rest = monsters_seen

        for child in _child_keys(node):
            if child in graph:
                queue.append((child, distance + 1, next_monsters, next_passed_rest))

    preview: JsonDict = {
        "nearest_shop": min_distance.get("Shop"),
        "nearest_rest": min_distance.get("RestSite"),
        "nearest_elite": min_distance.get("Elite"),
        "monsters_before_rest": min_monsters_before_rest,
        "reachable_counts": counts,
        "forced_nodes": _forced_nodes(start, graph, max_depth=6),
    }
    return preview


def _child_keys(node: JsonDict) -> list[tuple[int, int]]:
    children = _copy_list(node.get("children"))
    keys: list[tuple[int, int]] = []
    for child in children:
        if isinstance(child, (list, tuple)) and len(child) >= 2:
            try:
                keys.append((int(child[0]), int(child[1])))
            except (TypeError, ValueError):
                continue
        elif isinstance(child, dict):
            key = _node_key(child)
            if key is not None:
                keys.append(key)
    return keys


def _forced_nodes(start: tuple[int, int], graph: dict[tuple[int, int], JsonDict], *, max_depth: int) -> list[str]:
    result: list[str] = []
    current = start
    for _ in range(max_depth):
        node = graph.get(current)
        if not isinstance(node, dict):
            break
        result.append(str(node.get("type") or "Unknown"))
        children = _child_keys(node)
        if len(children) != 1:
            break
        current = children[0]
    return result
