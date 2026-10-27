from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from creator_lifecycle import AssetDecision, AssetRequest


def prepare_asset(request: AssetRequest, ttl_hours: int = 24) -> AssetDecision:
    if request.processing_state != "ready":
        raise ValueError("asset processing must be ready before delivery")
    return AssetDecision(
        key=f"{request.creator_id}/{request.asset_key}",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )


def subscriber_update(request: AssetRequest, decision: AssetDecision) -> dict:
    return {"subscriber_id": request.subscriber_id, "asset": asdict(decision)}
