import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        for key, env_value in os.environ.items():
            value = value.replace(f"${{{key}}}", env_value)
        return value
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        config_path = Path("config.example.yaml")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    return _expand_env(config)
