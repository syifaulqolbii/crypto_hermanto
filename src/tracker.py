import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.models import Signal


@dataclass
class ActiveSignal:
    signal: Signal
    created_at: float
    status: Literal["active", "tp1_hit", "tp2_hit", "sl_hit", "invalidated", "expired"] = "active"
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        data = asdict(self.signal)
        data["_status"] = self.status
        data["_created_at"] = self.created_at
        data["_updated_at"] = self.updated_at
        return data


class SignalTracker:
    def __init__(self, state_file: str = "logs/active_signals.json") -> None:
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._active: dict[str, ActiveSignal] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for key, item in data.items():
                status = item.pop("_status", "active")
                created_at = item.pop("_created_at", time.time())
                updated_at = item.pop("_updated_at", 0.0)
                signal = Signal(**item)
                self._active[key] = ActiveSignal(
                    signal=signal,
                    created_at=created_at,
                    status=status,
                    updated_at=updated_at,
                )
        except Exception as exc:
            print(f"[Tracker] Failed to load state: {exc}")

    def _save(self) -> None:
        try:
            data = {key: entry.to_dict() for key, entry in self._active.items()}
            with self.state_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[Tracker] Failed to save state: {exc}")

    def add(self, signal: Signal) -> None:
        self._active[signal.key()] = ActiveSignal(
            signal=signal,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._save()

    def get_active_for_symbol(self, symbol: str) -> list[ActiveSignal]:
        return [
            entry for entry in self._active.values()
            if entry.signal.symbol == symbol and entry.status == "active"
        ]

    def get_all_active(self) -> list[ActiveSignal]:
        return [entry for entry in self._active.values() if entry.status == "active"]

    def mark(self, key: str, status: str) -> None:
        if key in self._active:
            self._active[key].status = status
            self._active[key].updated_at = time.time()
            self._save()

    def has_active(self, symbol: str) -> bool:
        return any(
            entry.signal.symbol == symbol and entry.status == "active"
            for entry in self._active.values()
        )

    def check_price_hit(self, entry: ActiveSignal, current_price: float) -> str | None:
        signal = entry.signal
        if signal.side == "LONG":
            if current_price <= signal.stop_loss:
                return "sl_hit"
            if current_price >= signal.tp2:
                return "tp2_hit"
            if current_price >= signal.tp1:
                return "tp1_hit"
        else:
            if current_price >= signal.stop_loss:
                return "sl_hit"
            if current_price <= signal.tp2:
                return "tp2_hit"
            if current_price <= signal.tp1:
                return "tp1_hit"
        return None
