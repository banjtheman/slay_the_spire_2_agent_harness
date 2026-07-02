from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class TraceWriter:
    def __init__(self, trace_dir: Path, *, harness_name: str):
        trace_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = trace_dir / f"{timestamp}-{harness_name}.jsonl"

    def write(self, event: JsonDict) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)
