"""Independent checker: the violating request ids under limits.yaml's rule."""
import re
import sys
from datetime import datetime


def violations(log):
    by = {}
    for line in open(log):
        m = re.search(r"^(\S+) \S+\s+req=(\S+) tenant=(\S+) path=(\S+)", line)
        ts, rid, tenant, path = m.groups()
        if tenant == "ops" or path == "/health":
            continue
        by.setdefault(tenant, []).append((datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp(), rid))
    bad = []
    for tenant, xs in by.items():
        for i in range(5, len(xs)):
            if xs[i][0] - xs[i - 5][0] < 10:
                bad.append(xs[i][1])
    return bad


if __name__ == "__main__":
    print(violations(sys.argv[1]))
