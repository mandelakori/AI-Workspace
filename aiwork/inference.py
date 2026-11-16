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
