import os

import httpx

from src.models import Signal
from src.notifier.console import format_signal


class TelegramNotifier:
    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, signal: Signal) -> None:
        if not self.token or not self.chat_id:
            print("[TelegramNotifier] Token or chat_id not set, skipping.")
            return

        text = f"🚨 *SIGNAL DETECTED*\n\n```\n{format_signal(signal)}\n```"
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                response.raise_for_status()
        except Exception as exc:
            print(f"[TelegramNotifier] Failed to send: {exc}")
