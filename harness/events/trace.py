"""Structured, append-only JSONL events, no raw model prompts or secrets."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('', encoding='utf-8')
        self.events: list[dict] = []

    def record(self, agent: str, event: str, **details) -> None:
        entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'agent':agent,
                 'event':event, **details}
        self.events.append(entry)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry, sort_keys=True) + '\n')
