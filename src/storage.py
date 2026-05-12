import json
import time
from dataclasses import asdict
from pathlib import Path

from src.models import Signal


class SignalStore:
    def __init__(self, log_file: str, cooldown_minutes: int) -> None:
        self.log_file = Path(log_file)
        self.cooldown_seconds = cooldown_minutes * 60
        self.seen: dict[str, float] = {}
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def should_emit(self, signal: Signal) -> bool:
        now = time.time()
        last_seen = self.seen.get(signal.key())
        if last_seen and now - last_seen < self.cooldown_seconds:
            return False
        self.seen[signal.key()] = now
        return True

    def save(self, signal: Signal) -> None:
        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(signal), ensure_ascii=False) + "\n")
