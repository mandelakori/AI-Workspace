from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Protocol

from .http import HTTPFailure, request
from .lock import file_lock

BASE = "https://cloud.lambda.ai/api/v1"
TERMINAL = {"terminated", "terminating", "preempted"}
ID = re.compile(r"[a-zA-Z0-9_-]{1,80}")


class Provider(Protocol):
    def instances(self) -> list[dict]: ...
    def types(self) -> dict: ...
    def instance(self, instance_id: str) -> dict: ...
    def launch(self, body: dict) -> str: ...
    def terminate(self, instance_id: str) -> None: ...


def public_instance(row: dict) -> dict:
    return {k: row[k] for k in ("id", "name", "ip", "status", "region", "instance_type")
            if k in row}


@dataclass(frozen=True)
class Lambda:
    key_env: str = "LAMBDA_API_KEY"

    def call(self, route: str, method: str = "GET", body: dict | None = None):
        key = os.environ.get(self.key_env)
        if not key:
            raise ValueError(f"missing Lambda credential in {self.key_env}")
        for attempt in range(3 if method == "GET" else 1):
            try:
                return request(BASE + route, method, body, key, timeout=12)["data"]
            except HTTPFailure as exc:
                if exc.status not in {429, 502, 503, 504} or attempt == 2 or method != "GET":
                    raise
            except OSError:
                if attempt == 2 or method != "GET":
                    raise
            sleep(1.1 * 2 ** attempt)

    def instances(self) -> list[dict]:
        return [public_instance(row) for row in self.call("/instances")]

    def types(self) -> dict:
        return self.call("/instance-types")

    def instance(self, instance_id: str) -> dict:
        if not ID.fullmatch(instance_id):
            raise ValueError("invalid instance ID")
        return public_instance(self.call(f"/instances/{instance_id}"))

    def launch(self, body: dict) -> str:
        ids = self.call("/instance-operations/launch", "POST", body)["instance_ids"]
        if not isinstance(ids, list) or len(ids) != 1 or not ID.fullmatch(ids[0]):
            raise RuntimeError("unexpected Lambda launch response")
        return ids[0]

    def terminate(self, instance_id: str) -> None:
        if not ID.fullmatch(instance_id):
            raise ValueError("invalid instance ID")
        self.call("/instance-operations/terminate", "POST", {"instance_ids": [instance_id]})


@dataclass
class Lifecycle:
    provider: Provider
    config: dict
    state: Path

    @property
    def name(self) -> str:
        name = self.config.get("name", "")
        if not name.startswith("aiwork-") or not ID.fullmatch(name) or len(name) > 64:
            raise ValueError("choose a unique managed instance name beginning with aiwork-")
        return name

    @property
    def intent(self) -> Path:
        return self.state / f"{self.name}.launch-intent"

    def existing(self) -> dict | None:
        rows = [row for row in self.provider.instances()
                if row.get("name") == self.name and row.get("status") not in TERMINAL]
        if len(rows) > 1:
            raise RuntimeError("multiple instances share the configured managed name")
        return rows[0] if rows else None

    def plan(self) -> dict:
        cfg = self.config
        body = {"name": self.name, "instance_type_name": cfg["instance_type"],
                "region_name": cfg["region"], "ssh_key_names": [cfg["ssh_key_name"]]}
        if any(not isinstance(v, str) or not v.strip() for v in (
            body["instance_type_name"], body["region_name"], body["ssh_key_names"][0]
        )):
            raise ValueError("instance type, region and SSH key registration are required")
        if cfg.get("file_systems"):
            body["file_system_names"] = cfg["file_systems"]
        if cfg.get("image_id"):
            body["image"] = {"id": cfg["image_id"]}
        return body

    def acquire(self, timeout: float, *, allow_launch: bool) -> dict:
        deadline = monotonic() + timeout
        with file_lock(self.state / f"{self.name}.lock", timeout=timeout):
            if (self.state / "STOP").exists():
                raise RuntimeError("controller paused")
            row = self.existing()
            if row:
                instance_id = row["id"]
            else:
                if not allow_launch or self.config.get("allow_launch") is not True:
                    raise RuntimeError("managed A100 absent and launch disabled")
                if self.intent.exists():
                    raise RuntimeError("unresolved launch intent; reconcile in Lambda before removing it")
                body = self.plan()
                types = self.provider.types()
                available = types.get(body["instance_type_name"], {}).get("regions_with_capacity_available", [])
                if not any(region.get("name") == body["region_name"] for region in available):
                    raise RuntimeError("configured Lambda instance type has no capacity in the selected region")
                if user_data := self.config.get("user_data_file"):
                    path = Path(user_data)
                    if path.stat().st_size > 1_000_000:
                        raise ValueError("cloud-init file exceeds 1 MB")
                    body["user_data"] = path.read_text(encoding="utf-8")
                if (self.state / "STOP").exists() or monotonic() >= deadline:
                    raise RuntimeError("launch cancelled before submission")
                # A POST response may be lost after a successful launch. Preserve the intent
                # across interruptions and refuse a second launch until reconciliation.
                with self.intent.open("x", encoding="utf-8") as stream:
                    stream.write("pending\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    instance_id = self.provider.launch(body)
                except HTTPFailure as exc:
                    if 400 <= exc.status < 500 and exc.status != 408:
                        self.intent.unlink()
                    raise
                self.intent.write_text(instance_id + "\n", encoding="utf-8")
            while monotonic() < deadline and not (self.state / "STOP").exists():
                if row is None:
                    try:
                        row = self.provider.instance(instance_id)
                    except HTTPFailure as exc:
                        if exc.status != 404:
                            raise
                if row and row.get("status") == "active" and row.get("ip"):
                    ipaddress.IPv4Address(row["ip"])
                    self.intent.unlink(missing_ok=True)
                    return row
                if row and row.get("status") in TERMINAL | {"unhealthy"}:
                    raise RuntimeError(f"Lambda instance state: {row['status']}")
                row = None
                sleep(min(3.0, max(0, deadline - monotonic())))
            raise TimeoutError("Lambda instance readiness timed out or was stopped")

    def terminate(self, instance_id: str, *, apply: bool) -> dict:
        if apply and self.config.get("allow_terminate") is not True:
            raise ValueError("allow_terminate is disabled")
        with file_lock(self.state / f"{self.name}.lock"):
            existing = self.existing()
            if not existing or existing.get("id") != instance_id:
                raise ValueError("instance is outside the configured managed scope")
            if apply:
                self.provider.terminate(instance_id)
            return {"id": instance_id, "action": "terminate", "submitted": apply}
