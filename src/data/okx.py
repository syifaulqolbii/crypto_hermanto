import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from src.models import Candle


class OkxClient:
    def __init__(self, base_url: str = "https://www.okx.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = os.getenv("OKX_API_KEY", "")
        self.api_secret = os.getenv("OKX_API_SECRET", "")
        self.passphrase = os.getenv("OKX_API_PASSPHRASE", "")

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {}

        timestamp = self._timestamp()
        message = f"{timestamp}{method.upper()}{path}{body}"
        digest = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode()
        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }

    def get(self, path: str, params: dict[str, Any] | None = None, auth: bool = False) -> dict[str, Any]:
        query = ""
        if params:
            query = "?" + "&".join(f"{key}={value}" for key, value in params.items())
        request_path = f"{path}{query}"
        headers = self._headers("GET", request_path) if auth else {}
        with httpx.Client(timeout=20) as client:
            response = client.get(f"{self.base_url}{path}", params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != "0":
            raise RuntimeError(f"OKX error {payload.get('code')}: {payload.get('msg')}")
        return payload

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        payload = self.get(
            "/api/v5/market/candles",
            {"instId": symbol, "bar": timeframe, "limit": min(limit, 300)},
        )
        candles = []
        for row in payload.get("data", []):
            candles.append(
                Candle(
                    ts=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    closed=row[8] == "1" if len(row) > 8 else True,
                )
            )
        return list(reversed(candles))

    def fetch_swap_symbols(self) -> list[str]:
        payload = self.get("/api/v5/public/instruments", {"instType": "SWAP"})
        symbols = [item["instId"] for item in payload.get("data", []) if item.get("settleCcy") == "USDT"]
        return sorted(symbols)
