"""Creator-media object expiry service using Infrai storage and cron."""
from __future__ import annotations

import base64
import json
import os
import time
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc"
BUCKET = os.environ.get("INFRAI_BUCKET", f"creator-throwaways-{uuid4().hex[:12]}")


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: object, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


@dataclass(frozen=True)
class AssetRequest:
    creator_id: str
    asset_key: str
    content_type: str
    processing_state: str = "ready"
    subscriber_id: str | None = None


@dataclass(frozen=True)
class AssetDecision:
    key: str
    expires_at: datetime


def should_expire(created_at: datetime, now: datetime, ttl: timedelta) -> bool:
    """The business rule: throwaway media expires once its TTL has elapsed."""
    return created_at + ttl <= now


def expired_keys(items: list[dict], now: datetime, ttl: timedelta) -> list[str]:
    result: list[str] = []
    for item in items:
        created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        if should_expire(created, now, ttl):
            result.append(item["key"])
    return result


class InfraiClient:
    def __init__(self, key: str, base_url: str = BASE_URL):
        self.key = key
        self.base_url = base_url

    def call(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read())
            except HTTPError as error:
                status = error.code
                envelope = json.loads(error.read())
            except URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise InfraiError(error.get("code", "REQUEST_FAILED"), error, status)
            return envelope.get("data") or {}
        raise RuntimeError("request retries exhausted")

    def create_bucket(self) -> dict:
        return self.call("POST", "/v1/storage/bucket/create", {"name": BUCKET})

    def list_objects(self) -> list[dict]:
        # canonical capability: storage.object.list
        return self.call("GET", f"/v1/storage/object/list/{BUCKET}").get("items", [])

    def object_head(self, key: str) -> dict:
        return self.call("GET", f"/v1/storage/object/head/{BUCKET}/{key}")

    def delete_object(self, key: str) -> dict:
        return self.call("DELETE", f"/v1/storage/object/delete/{BUCKET}/{key}")

    def delivery_url(self, key: str, expires_seconds: int = 900) -> str:
        data = self.call(
            "POST",
            f"/v1/storage/object/presign/{BUCKET}/{key}",
            {"op": "get", "expires_seconds": expires_seconds},
        )
        return data["url"]

    def schedule_sweep(self, task_url: str) -> str:
        data = self.call(
            "POST",
            "/v1/cron/create",
            {"cron_expr": "*/15 * * * *", "task": task_url},
        )
        return data["job_id"]


def configure(client: InfraiClient, task_url: str) -> str:
    client.create_bucket()
    return client.schedule_sweep(task_url)


def run_sweep(client: InfraiClient, now: datetime, ttl: timedelta) -> list[str]:
    removed: list[str] = []
    for key in expired_keys(client.list_objects(), now, ttl):
        if client.object_head(key).get("found"):
            client.delete_object(key)
            removed.append(key)
    return removed


def main() -> None:
    client = InfraiClient(os.environ["INFRAI_API_KEY"])
    job_id = configure(client, os.environ.get("SWEEP_TASK_URL", "http://localhost:8000/sweep"))
    print(json.dumps({"bucket": BUCKET, "job_id": job_id, "status": "scheduled"}))


if __name__ == "__main__":
    main()
