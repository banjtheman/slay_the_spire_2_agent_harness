from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .normalize import JsonDict, normalize_state


class BridgeApiError(RuntimeError):
    """Raised when the live in-game bridge is unavailable or rejects an action."""


class LiveSts2Client:
    """Client for STS2_Bridge running inside the visible Slay the Spire 2 app."""

    def __init__(self, base_url: str = "http://localhost:15526", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def singleplayer_url(self) -> str:
        return f"{self.base_url}/api/v1/singleplayer"

    def raw_state(self, *, format: str = "json") -> JsonDict | str:
        query = urllib.parse.urlencode({"format": format})
        url = f"{self.singleplayer_url}?{query}"
        if format == "json":
            return self._request_json("GET", url)
        return self._request_text("GET", url)

    def state(self) -> JsonDict:
        raw = self.raw_state(format="json")
        if not isinstance(raw, dict):
            raise BridgeApiError("Expected JSON object from bridge state endpoint")
        return normalize_state(raw)

    def post_action(self, action: str, **payload: Any) -> JsonDict:
        if "action" in payload:
            raise ValueError("Pass action as the first argument, not inside payload")
        body: JsonDict = {**payload, "action": action}
        return self._request_json("POST", self.singleplayer_url, body)

    def send(self, command: JsonDict) -> JsonDict:
        """Accept a headless-style command and apply it to the visible game."""
        cmd = command.get("cmd")
        if cmd == "state":
            return self.state()
        if cmd == "raw_state":
            raw = self.raw_state(format="json")
            if not isinstance(raw, dict):
                raise BridgeApiError("Expected JSON object from bridge state endpoint")
            return raw
        if cmd == "start_run":
            character = str(command.get("character") or "Ironclad").upper()
            ascension = int(command.get("ascension") or 0)
            return self.start_new_run(character=character, ascension=ascension)
        if cmd == "continue_game":
            return self._post_and_refresh("continue_game")
        if cmd == "quit":
            return {
                "type": "quit_result",
                "success": True,
                "live": True,
                "message": "Live mode leaves the real game running.",
            }
        if cmd != "action":
            raise BridgeApiError(f"Unsupported live command: {cmd}")

        action = str(command.get("action") or "")
        args = command.get("args") if isinstance(command.get("args"), dict) else {}
        return self.send_action(action, **args)

    def send_action(self, action: str, **args: Any) -> JsonDict:
        """Translate common sts2-cli action names to STS2_Bridge actions."""
        if action == "wait":
            seconds = float(args.get("seconds", 1.0))
            time.sleep(max(0.0, min(seconds, 10.0)))
            return self.state()

        if action == "play_card":
            card_index = int(args["card_index"])
            target = args.get("target")
            if target is None and "target_index" in args:
                target = self._enemy_id_from_index(int(args["target_index"]))
            payload = {"card_index": card_index}
            if target is not None:
                payload["target"] = target
            return self._post_and_refresh("play_card", **payload)

        if action == "use_potion":
            slot = int(args.get("slot", args.get("potion_index", 0)))
            target = args.get("target")
            if target is None and "target_index" in args:
                target = self._enemy_id_from_index(int(args["target_index"]))
            payload = {"slot": slot}
            if target is not None:
                payload["target"] = target
            return self._post_and_refresh("use_potion", **payload)

        if action == "end_turn":
            return self._post_and_refresh("end_turn")
        if action == "select_map_node":
            index = args.get("index")
            if index is None:
                index = self._map_choice_index(args)
            return self._post_and_refresh("choose_map_node", index=int(index))
        if action == "choose_option":
            return self._choose_contextual_option(int(args["option_index"]))
        if action == "choose_event_option":
            return self._post_and_refresh("choose_event_option", index=int(args["index"]))
        if action == "choose_rest_option":
            return self._post_and_refresh("choose_rest_option", index=int(args["index"]))
        if action == "advance_dialogue":
            return self._post_and_refresh("advance_dialogue")
        if action in {"leave_room", "proceed"}:
            self._validate_proceed()
            return self._post_and_refresh("proceed")
        if action == "claim_reward":
            return self._claim_reward(int(args["index"]))
        if action == "select_card_reward":
            return self._post_and_refresh("select_card_reward", card_index=int(args["card_index"]))
        if action == "skip_card_reward":
            return self._post_and_refresh("skip_card_reward")
        if action in {"buy_card", "buy_relic", "buy_potion", "remove_card", "shop_purchase"}:
            index = self._shop_index_for(action, args)
            return self._post_and_refresh("shop_purchase", index=index)
        if action == "select_cards":
            return self._select_cards(str(args.get("indices", "")))
        if action == "skip_select":
            return self._post_and_refresh("cancel_selection")
        if action == "select_card":
            index = args.get("index", args.get("card_index"))
            if index is None:
                raise BridgeApiError("select_card requires index or card_index")
            result = self._post_and_refresh("select_card", index=int(index))
            if result.get("decision") == "card_select" and result.get("can_confirm", False):
                return self._post_and_refresh("confirm_selection")
            return result
        if action == "confirm_selection":
            return self._post_and_refresh("confirm_selection")
        if action == "cancel_selection":
            return self._post_and_refresh("cancel_selection")
        if action == "combat_select_card":
            result = self._post_and_refresh("combat_select_card", card_index=int(args["card_index"]))
            if result.get("decision") == "hand_select" and result.get("can_confirm", False):
                return self._post_and_refresh("combat_confirm_selection")
            return result
        if action == "combat_confirm_selection":
            return self._post_and_refresh("combat_confirm_selection")
        if action == "select_relic":
            return self._post_and_refresh("select_relic", index=int(args["index"]))
        if action == "skip_relic_selection":
            return self._post_and_refresh("skip_relic_selection")
        if action == "claim_treasure_relic":
            state = self.state()
            if (
                state.get("decision") == "treasure"
                and state.get("relics") == []
                and state.get("can_proceed", False)
            ):
                return self._post_and_refresh("proceed")
            return self._post_and_refresh("claim_treasure_relic", index=int(args["index"]))
        if action == "continue_game":
            return self._post_and_refresh("continue_game")
        if action == "abandon_game":
            return self._post_and_refresh("abandon_game")
        if action == "return_to_main_menu":
            return self._post_and_refresh("return_to_main_menu")
        if action == "start_new_game":
            character = str(args.get("character") or "IRONCLAD").upper()
            ascension = int(args.get("ascension") or 0)
            return self.start_new_run(character=character, ascension=ascension)

        return self._post_and_refresh(action, **args)

    def start_new_run(self, *, character: str = "IRONCLAD", ascension: int = 0) -> JsonDict:
        state = self.state()
        previous_context = state.get("context") if isinstance(state.get("context"), dict) else {}

        if state.get("decision") != "menu":
            state = self._return_to_menu()

        if state.get("decision") == "menu" and state.get("can_abandon_game"):
            self._post_and_refresh("abandon_game")
        try:
            return self._post_and_refresh("start_new_game", character=character.upper(), ascension=int(ascension))
        except BridgeApiError as exc:
            current = self.state()
            context = current.get("context") if isinstance(current.get("context"), dict) else {}
            if (
                "Main menu is not open" in str(exc)
                and current.get("decision") != "menu"
                and context.get("act") is not None
                and _looks_like_fresh_run(context, previous_context, int(ascension))
            ):
                current["_last_action_result"] = {
                    "status": "ok",
                    "message": "Starting run left the main menu before the bridge returned",
                }
                return current
            raise

    def _return_to_menu(self) -> JsonDict:
        state: JsonDict = {}
        last_error: BridgeApiError | None = None
        for _ in range(4):
            try:
                state = self._post_and_refresh("return_to_main_menu")
            except BridgeApiError as exc:
                last_error = exc
                time.sleep(0.5)
                continue
            if state.get("decision") == "menu":
                return state
            time.sleep(0.5)
        if state:
            return state
        if last_error is not None:
            raise last_error
        return self.state()

    def doctor(self) -> JsonDict:
        try:
            state = self.state()
        except BridgeApiError as exc:
            return {
                "ok": False,
                "base_url": self.base_url,
                "error": str(exc),
                "next_steps": [
                    "Install STS2_Bridge into the game.",
                    "Launch Slay the Spire 2 from Steam.",
                    "Enable the STS2_Bridge mod in the game's mod manager.",
                    "Wait for the mod to start listening on localhost:15526.",
                ],
            }
        return {
            "ok": True,
            "base_url": self.base_url,
            "decision": state.get("decision"),
            "context": state.get("context"),
        }

    def _post_and_refresh(self, action: str, **payload: Any) -> JsonDict:
        before = self._safe_state_signature()
        result = self.post_action(action, **payload)
        if result.get("status") == "error":
            raise BridgeApiError(str(result.get("error") or result))
        refreshed = self._wait_for_refresh(before, after_action=action)
        refreshed["_last_action_result"] = result
        return refreshed

    def _safe_state_signature(self) -> tuple[Any, ...] | None:
        try:
            return self._state_signature(self.state())
        except BridgeApiError:
            return None

    def _wait_for_refresh(self, before: tuple[Any, ...] | None, *, after_action: str | None = None) -> JsonDict:
        timeout = 10.0 if after_action in {"choose_map_node", "start_new_game", "return_to_main_menu"} else 5.0
        deadline = time.monotonic() + timeout
        latest: JsonDict | None = None
        last_error: BridgeApiError | None = None
        while time.monotonic() < deadline:
            try:
                latest = self.state()
            except BridgeApiError as exc:
                last_error = exc
                time.sleep(0.15)
                continue
            signature = self._state_signature(latest)
            if (
                (before is None or signature != before)
                and not self._is_transitional_state(latest)
                and not self._is_transitional_after_action(latest, after_action)
            ):
                return self._settle_state(latest, after_action=after_action)
            time.sleep(0.15)
        if latest is not None:
            return latest
        if last_error is not None:
            raise last_error
        raise BridgeApiError("Timed out waiting for STS2_Bridge to return a refreshed state")

    @staticmethod
    def _is_transitional_state(state: JsonDict) -> bool:
        if state.get("decision") == "unknown":
            return True
        if state.get("decision") == "combat_play" and not state.get("is_play_phase", True):
            return True
        if state.get("decision") == "combat_rewards":
            return state.get("items") == [] and not state.get("can_proceed", False)
        if state.get("decision") == "event_choice":
            options = state.get("options")
            if options == [] and not state.get("in_dialogue", False):
                return True
        return False

    @staticmethod
    def _is_transitional_after_action(state: JsonDict, action: str | None) -> bool:
        if action == "choose_map_node" and state.get("decision") == "map_select":
            return True
        if action == "proceed" and state.get("decision") == "combat_rewards":
            return True
        if action == "start_new_game" and state.get("decision") == "menu":
            return True
        if action == "return_to_main_menu" and state.get("decision") != "menu":
            return True
        return False

    def _settle_state(self, latest: JsonDict, *, after_action: str | None) -> JsonDict:
        if after_action is None:
            return latest
        settle_until = time.monotonic() + 0.5
        settled = latest
        while time.monotonic() < settle_until:
            time.sleep(0.1)
            try:
                candidate = self.state()
            except BridgeApiError:
                continue
            if self._is_transitional_state(candidate) or self._is_transitional_after_action(candidate, after_action):
                continue
            settled = candidate
        return settled

    @staticmethod
    def _state_signature(state: JsonDict) -> tuple[Any, ...]:
        enemies = state.get("enemies")
        enemy_sig = ()
        if isinstance(enemies, list):
            enemy_sig = tuple(
                (enemy.get("entity_id") or enemy.get("id"), enemy.get("hp"), enemy.get("block"))
                for enemy in enemies
                if isinstance(enemy, dict)
            )
        hand = state.get("hand")
        hand_sig = ()
        if isinstance(hand, list):
            hand_sig = tuple(
                (card.get("index"), card.get("id"), card.get("name"))
                for card in hand
                if isinstance(card, dict)
            )
        choices = state.get("choices")
        choice_sig = ()
        if isinstance(choices, list):
            choice_sig = tuple(
                (choice.get("index"), choice.get("col"), choice.get("row"), choice.get("type"))
                for choice in choices
                if isinstance(choice, dict)
            )
        player = state.get("player") if isinstance(state.get("player"), dict) else {}
        return (
            state.get("decision"),
            state.get("screen"),
            state.get("can_continue_game"),
            state.get("can_abandon_game"),
            state.get("can_start_new_game"),
            state.get("room_type"),
            state.get("round"),
            state.get("turn"),
            state.get("energy"),
            state.get("context", {}).get("act") if isinstance(state.get("context"), dict) else None,
            state.get("context", {}).get("floor") if isinstance(state.get("context"), dict) else None,
            player.get("hp"),
            player.get("block"),
            len(hand) if isinstance(hand, list) else None,
            enemy_sig,
            choice_sig,
            hand_sig,
        )

    def _enemy_id_from_index(self, target_index: int) -> str:
        state = self.state()
        enemies = state.get("enemies")
        if not isinstance(enemies, list):
            raise BridgeApiError(f"Invalid target_index {target_index}")
        if 0 <= target_index < len(enemies):
            enemy = enemies[target_index]
            if not isinstance(enemy, dict):
                raise BridgeApiError(f"Invalid enemy row for target_index {target_index}")
            entity_id = enemy.get("entity_id") or enemy.get("id")
            if not entity_id:
                raise BridgeApiError(f"Enemy {target_index} has no entity_id in live bridge state")
            return str(entity_id)

        for enemy in enemies:
            if not isinstance(enemy, dict):
                continue
            if enemy.get("combat_id") == target_index:
                entity_id = enemy.get("entity_id") or enemy.get("id")
                if entity_id:
                    return str(entity_id)

        if len(enemies) == 1:
            enemy = enemies[0]
            if isinstance(enemy, dict):
                entity_id = enemy.get("entity_id") or enemy.get("id")
                if entity_id:
                    return str(entity_id)
        raise BridgeApiError(f"Invalid target_index {target_index}")

    def _map_choice_index(self, args: JsonDict) -> int:
        choices = self.state().get("choices")
        if not isinstance(choices, list):
            raise BridgeApiError("Current live state is not map_select")
        col = args.get("col")
        row = args.get("row")
        for i, choice in enumerate(choices):
            if not isinstance(choice, dict):
                continue
            coordinate = choice.get("coordinate") if isinstance(choice.get("coordinate"), dict) else choice
            if coordinate.get("col") == col and coordinate.get("row") == row:
                return i
        raise BridgeApiError(f"No live map choice matches col={col} row={row}")

    def _choose_contextual_option(self, option_index: int) -> JsonDict:
        decision = self.state().get("decision")
        if decision == "event_choice":
            return self._post_and_refresh("choose_event_option", index=option_index)
        if decision == "rest_site":
            return self._post_and_refresh("choose_rest_option", index=option_index)
        raise BridgeApiError(f"choose_option is ambiguous for live decision {decision!r}")

    def _shop_index_for(self, action: str, args: JsonDict) -> int:
        if action == "shop_purchase":
            return int(args["index"])
        state = self.state()
        if action == "remove_card":
            item = state.get("card_removal")
            if not isinstance(item, dict) or "index" not in item:
                raise BridgeApiError("No card removal item is available")
            return int(item["index"])
        category_key = {
            "buy_card": ("cards", "card_index"),
            "buy_relic": ("relics", "relic_index"),
            "buy_potion": ("potions", "potion_index"),
        }[action]
        rows = state.get(category_key[0])
        requested = int(args[category_key[1]])
        if not isinstance(rows, list):
            raise BridgeApiError("Current live state is not shop")
        for row in rows:
            if isinstance(row, dict) and int(row.get("index", -1)) == requested:
                return requested
        if 0 <= requested < len(rows) and isinstance(rows[requested], dict):
            return int(rows[requested]["index"])
        raise BridgeApiError(f"No shop {category_key[0]} entry for index {requested}")

    def _claim_reward(self, index: int) -> JsonDict:
        state = self.state()
        if state.get("decision") == "combat_rewards":
            items = state.get("items")
            player = state.get("player") if isinstance(state.get("player"), dict) else {}
            if isinstance(items, list):
                selected = next((item for item in items if isinstance(item, dict) and item.get("index") == index), None)
                if selected is not None and selected.get("type") == "potion" and int(player.get("open_potion_slots") or 0) <= 0:
                    for item in items:
                        if isinstance(item, dict) and item.get("type") != "potion":
                            return self._post_and_refresh("claim_reward", index=int(item["index"]))
                    if state.get("can_proceed", False):
                        return self._post_and_refresh("proceed")
        return self._post_and_refresh("claim_reward", index=index)

    def _select_cards(self, indices: str) -> JsonDict:
        parsed = [int(part.strip()) for part in indices.split(",") if part.strip()]
        state = self.state()
        decision = state.get("decision")
        last: JsonDict | None = None
        if decision == "hand_select":
            for index in parsed:
                last = self._post_and_refresh("combat_select_card", card_index=index)
            if (last or state).get("can_confirm", False) or self.state().get("can_confirm", False):
                return self._post_and_refresh("combat_confirm_selection")
            return last or self.state()
        if decision == "card_select":
            for index in parsed:
                last = self._post_and_refresh("select_card", index=index)
            current = self.state()
            if current.get("can_confirm", False):
                return self._post_and_refresh("confirm_selection")
            return last or current
        raise BridgeApiError(f"select_cards is invalid for live decision {decision!r}")

    def _validate_proceed(self) -> None:
        state = self.state()
        if state.get("decision") != "combat_rewards":
            return
        items = state.get("items")
        player = state.get("player") if isinstance(state.get("player"), dict) else {}
        open_slots = int(player.get("open_potion_slots") or 0)
        if isinstance(items, list) and items:
            if state.get("can_proceed", False) and open_slots <= 0 and _only_potion_rewards(items):
                return
            raise BridgeApiError("Reward items remain; claim or inspect rewards before proceeding")
        if items == [] and not state.get("can_proceed", False):
            raise BridgeApiError("Reward screen has no items and no enabled proceed button")

    def _request_text(self, method: str, url: str, body: JsonDict | None = None) -> str:
        req = urllib.request.Request(url, method=method)
        if body is None:
            data = None
        else:
            data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, data=data, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise BridgeApiError(f"HTTP {exc.code}: {text}") from exc
        except urllib.error.URLError as exc:
            raise BridgeApiError(
                "Cannot connect to STS2_Bridge. Is the visible game running with the bridge mod enabled?"
            ) from exc
        except TimeoutError as exc:
            raise BridgeApiError(
                "STS2_Bridge request timed out. The in-game bridge may be busy or wedged; restart Slay the Spire 2 if this persists."
            ) from exc

    def _request_json(self, method: str, url: str, body: JsonDict | None = None) -> JsonDict:
        text = self._request_text(method, url, body)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BridgeApiError(f"Expected JSON response, got: {text[:200]}") from exc
        if not isinstance(data, dict):
            raise BridgeApiError(f"Expected JSON object response, got {type(data).__name__}")
        return data


def _looks_like_fresh_run(context: JsonDict, previous_context: JsonDict, ascension: int) -> bool:
    if int(context.get("ascension") or 0) != int(ascension):
        return False
    if int(context.get("act") or 0) != 1:
        return False
    floor = context.get("floor")
    if floor in (0, 1):
        return True
    return context != previous_context


def _only_potion_rewards(items: list[Any]) -> bool:
    found = False
    for item in items:
        if not isinstance(item, dict):
            return False
        if item.get("type") != "potion":
            return False
        found = True
    return found
