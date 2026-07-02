from __future__ import annotations

import re
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def load_encounter_notes(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def select_encounter_notes(notes: str, state: JsonDict, *, max_chars: int = 2400) -> str:
    if not notes.strip():
        return ""

    haystack = _state_haystack(state)
    sections = _split_sections(notes)
    selected: list[str] = []
    for title, body in sections:
        title_key = title.lower()
        terms = _section_terms(title, body)
        if title_key in {"global", "general", "general rules", "boss rules", "elite rules"}:
            selected.append(f"## {title}\n{body}".strip())
            continue
        if any(term and term in haystack for term in terms):
            selected.append(f"## {title}\n{body}".strip())

    if not selected:
        return ""
    text = "\n\n".join(selected)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n..."


def _split_sections(notes: str) -> list[tuple[str, str]]:
    matches = list(_SECTION_RE.finditer(notes))
    if not matches:
        return [("General", notes.strip())]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(notes)
        title = match.group(1).strip()
        body = notes[start:end].strip()
        sections.append((title, body))
    return sections


def _section_terms(title: str, body: str) -> set[str]:
    terms = {_normalize_term(title)}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() not in {"aliases", "triggers"}:
            continue
        for term in value.split(","):
            normalized = _normalize_term(term)
            if normalized:
                terms.add(normalized)
    return terms


def _state_haystack(state: JsonDict) -> str:
    values: list[str] = []

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {
                    "name",
                    "id",
                    "entity_id",
                    "room_type",
                    "screen_type",
                    "title",
                    "type",
                    "description",
                }:
                    values.append(str(item))
                if key in {"enemies", "status", "powers", "hand", "cards", "relics", "potions", "intents"}:
                    walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    walk(state)
    return "\n".join(_normalize_term(value) for value in values)


def _normalize_term(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")
