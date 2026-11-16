from __future__ import annotations

import os
from dataclasses import dataclass

from .http import request
from .schema import Profile


@dataclass(frozen=True)
class Inference:
    profile: Profile

    def key(self) -> str:
        name = self.profile.api_key_env
        if name and not os.environ.get(name):
            raise ValueError(f"missing endpoint credential in {name}")
        return os.environ[name] if name else ""

    def models(self) -> list[dict]:
        return request(self.profile.endpoint.rstrip("/") + "/models", key=self.key())["data"]

    def ready(self) -> None:
        if not any(row.get("id") == self.profile.model for row in self.models()):
            raise ValueError(f"configured model missing from {self.profile.id} inventory")


def ollama_inventory(endpoint: str) -> dict:
    root = endpoint.rstrip("/").removesuffix("/v1")
    return {"installed": request(root + "/api/tags")["models"],
            "resident": request(root + "/api/ps")["models"]}


def ollama_residency(profile: Profile) -> dict | None:
    root = profile.endpoint.rstrip("/").removesuffix("/v1")
    try:
        rows = request(root + "/api/ps", timeout=3)["models"]
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and profile.model in (row.get("name"), row.get("model")):
                size = row.get("size_vram")
                context = row.get("context_length")
                return {"resident": True,
                        "model_vram_mib": round(size / (1024 ** 2)) if type(size) is int else None,
                        "configured_server_context": context if type(context) is int else None}
        return {"resident": False}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return None
