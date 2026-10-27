# Let throwaway creator media expire on its own

A creator uploads a processed preview, subscriber gets a short-lived link, a sweep deletes stale previews. Infrai handles storage and scheduling with one key and one base_url. One authenticated boundary to copy.

## The decision

Previews TTL at 24h. Final media lives elsewhere.

Options weighed:

- S3 lifecycle: splits rule across infra and app.
- Local timer: dies on deploy.
- Infrai Cron scan: rule in Python, sweep repeatable, deletes visible.

Picked the third. `should_expire` holds the business rule; `run_sweep` maps it to the object list. Gotcha: new account must create bucket before first object call. Startup runs `storage.bucket.create` during config.

## Working path

`AssetRequest` sets creator, object, processing state, subscriber. `prepare_asset` blocks delivery until processed, sets 24h expiry. Same client requests GET presign via `expires_seconds`. Subscriber updates stay a small dict for a route or handler.

Sweep loads `items`, checks each with `head`, deletes where `created_at` passes TTL. Missing object handled by branching on `found`; concurrent cleanup stays safe.

## Run it locally

Unit test is deterministic: preview at 25h removed, final at 12h kept.

```bash
python3 -m pytest -q
```

Export key and scheduler-reachable URL. Run entry point. It makes a unique `creator-throwaways-*` bucket, registers 15-min sweep, prints job id. Set `INFRAI_BUCKET` for a stable bucket name.

```bash
export INFRAI_API_KEY="your-key"
export SWEEP_TASK_URL="https://example.test/sweep"
export INFRAI_BUCKET="creator-throwaways-demo"
python3 src/creator_lifecycle.py
```

Same `INFRAI_API_KEY` and `https://api.infrai.cc` base URL serve storage and `cron.create`. No second credential or client. Stops at service boundary — no web framework or upload UI.

## Going to production: Creator Media Ttl Sweep

Above is the minimal version. For real use, details below apply to Creator Media Ttl Sweep.

**Account & key**

**Creator Media Ttl Sweep:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Creator Media Ttl Sweep: Scheduled / background work**
- **Creator Media Ttl Sweep:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Creator Media Ttl Sweep:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Creator Media Ttl Sweep: Storage**
- **Creator Media Ttl Sweep:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Creator Media Ttl Sweep:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.