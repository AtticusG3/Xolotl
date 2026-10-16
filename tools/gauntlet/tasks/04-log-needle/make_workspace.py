"""Generates workspace/service.log + workspace/limits.yaml (deterministic) and the answer (hidden/answer.txt)."""
import random
from datetime import datetime, timedelta, timezone

R = random.Random(20261016)
T0 = datetime(2026, 10, 16, 3, 0, 0, tzinfo=timezone.utc)
TENANTS = ["acme", "globex", "initech", "umbrella", "hooli", "stark", "wayne"]
PATHS = ["/api/orders", "/api/users", "/api/search", "/api/cart", "/api/pay"]
lines = []   # (seconds_from_t0, tenant, path, status, ms)


def add(t, tenant, path, status=200):
    lines.append((round(t, 3), tenant, path, status, R.randint(3, 900)))


# background traffic: every tenant spaced so it never exceeds 4 counted requests per 10 s
QUIET = {"hooli": (285, 320), "wayne": (485, 525), "stark": (625, 665), "initech": (685, 725)}   # staged bursts below
for tenant in TENANTS:
    t = R.uniform(0, 3)
    while t < 760:
        q = QUIET.get(tenant)
        if not (q and q[0] <= t <= q[1]):
            add(t, tenant, R.choice(PATHS), R.choice([200] * 12 + [404, 500, 429]))
        t += R.uniform(3.5, 12.0)
# distractor 1: ops is exempt - a burst of 12 in 3 s
for i in range(12):
    add(120 + i * 0.25, "ops", "/api/admin/reindex")
# distractor 2: hooli 5 api + 4 /health inside 6 s (health is not counted -> 5 counted, legal)
for i in range(9):
    add(300 + i * 0.7, "hooli", "/health" if i % 2 else "/api/search")
# distractor 3: wayne 6 requests whose 1st and 6th are EXACTLY 10.000 s apart (half-open window -> legal)
for t in [500.0, 502.5, 504.0, 506.25, 508.75, 510.0]:
    add(t, "wayne", "/api/cart")
# distractor 4: a loud failure cluster (errors, not a rate-limit violation)
for i in range(4):
    add(640 + i * 3.1, "stark", "/api/pay", 500)
# THE needle: initech, 6 counted requests in 9.8 s, one of them a 429 (rejections still count)
needle_times = [700.4, 702.1, 703.3, 705.9, 708.0, 710.2]
for i, t in enumerate(needle_times):
    add(t, "initech", "/api/orders", 429 if i == 3 else 200)
lines.sort()
out, ids = [], []
for k, (t, tenant, path, status, ms) in enumerate(lines):
    rid = "%08x" % R.getrandbits(32)
    ids.append(rid)
    ts = (T0 + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % round((t % 1) * 1000)
    level = "ERROR" if status >= 500 else ("WARN" if status in (404, 429) else "INFO")
    out.append(f"{ts} {level:5s} req={rid} tenant={tenant} path={path} status={status} ms={ms}")
open("workspace/service.log", "w").write("\n".join(out) + "\n")
open("workspace/limits.yaml", "w").write(
    "# Rate limits (gateway v3).\n"
    "# Limits are per tenant: at most `per_tenant` COUNTED requests in any window of `window_s` seconds.\n"
    "# A window is half-open: [t, t + window_s). The request that would be the (per_tenant + 1)-th inside a\n"
    "# window is a VIOLATION. Requests rejected by the gateway (status 429) still count.\n"
    "# Not counted at all: every request of tenant `ops`, and every request to the path `/health`.\n"
    "rate_limit:\n  per_tenant: 5\n  window_s: 10\n")
