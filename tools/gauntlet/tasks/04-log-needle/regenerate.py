#!/usr/bin/env python3
"""Builds every generated artifact of 04-log-needle and cross-checks the design.

  1. make_workspace.generate() writes the workspace files from the fixed seed
  2. checker.py - an independent reader of THOSE files - derives the answer
  3. this script asserts the checker's result matches the generator's INTENT (which epoch
     each violation comes from) and that every rule class decides at least one id, so a
     drift between the two descriptions fails loudly instead of shipping a wrong answer
  4. hidden/answer.txt and reference/ANSWER.txt take the checker's answer; trap/ANSWER.txt
     takes the single-rule scan - plausible, format-legal, and wrong

  python3 regenerate.py [--table]
"""
import sys
from pathlib import Path

import checker
import make_workspace as M

HERE = Path(__file__).resolve().parent


def single_rule_scan(ws: Path) -> list:
    """The trap: a scan that reads limits.yaml's per-tenant rule only.

    It treats the log's own field (the API key) as the tenant, counts every line it finds
    - ops traffic, /health probes, retired-key 403s, exempt maintenance traffic - and
    never applies the global limit. Every id it reports is a request of a key with too
    many requests in a 10 s window; there is no reason for a model to distrust it.
    """
    limits, _keys, _exempt, ev = checker.load(ws)
    per = {}
    for e in ev:
        per.setdefault(e["key"], []).append((e["t"], e["id"]))
    n, window = limits["per_tenant"], limits["window_s"] * 1_000
    out = set()
    for stream in per.values():
        stream.sort()
        for i in range(n, len(stream)):
            if stream[i][0] - stream[i - n][0] < window:
                out.add(stream[i][1])
    return sorted(out)


def main(show_table=False):
    meta = M.write(HERE / "workspace")
    limits, keys, exempt, ev = checker.load(HERE / "workspace")
    full = checker.flag(ev, limits, keys, exempt)
    per_only = checker.flag(ev, limits, keys, exempt, global_rule=False)
    no_exempt = checker.flag(ev, limits, keys, exempt, exempt_ranges=False)
    by_key = checker.flag(ev, limits, keys, exempt, join=False)
    no_retired = checker.flag(ev, limits, keys, exempt, retired=False)
    global_only = checker.flag(ev, limits, keys, exempt, per_tenant=False)

    want = {meta["acme-join"][-1],                       # the 6th counted acme request, only
            *meta["globex-per"][-2:],                    # visible once both keys are joined
            meta["storm-a"][-1], meta["storm-b"][-1]}    # 18 counted in a 10 s window
    assert full == want, f"answer drifted: {sorted(full)} != {sorted(want)}"
    assert not full & set(meta["ops-burst"] + meta["hooli-health"]
                          + meta["wayne-halfopen"] + meta["stark-errors"]), \
        "a decoy epoch produced a violation - a decoy is legal by construction"
    assert per_only == {meta["acme-join"][-1], *meta["globex-per"][-2:]}
    assert global_only == {meta["storm-a"][-1], meta["storm-b"][-1]}
    decisions = {                        # each rule class, and the ids it alone decides
        "per-tenant rule decides": full - global_only,
        "global rule decides": full - per_only,
        "exemption file excludes": no_exempt - full,
        "join reveals": full - by_key,
        "retired-key rule excludes": no_retired - full,
    }
    assert all(decisions.values()), f"a rule class decides nothing: {decisions}"
    assert set(meta["hooli-exempt"][-2:]) == no_exempt - full          # exemption excludes 2
    assert set(meta["initech-retired"][-1:]) <= no_retired - full      # retired key: last one only
    assert meta["acme-join"][-1] in full - by_key                      # join reveals acme's 6th
    assert not (by_key - full) & set(meta["acme-join"] + meta["globex-per"]), \
        "key-grouping must not invent per-tenant violations of a real tenant"

    trap = single_rule_scan(HERE / "workspace")
    assert trap != sorted(full) and trap, "the trap must be a different, non-empty set"

    body = "\n".join(sorted(full)) + "\n"
    (HERE / "hidden" / "answer.txt").write_text(body)
    (HERE / "reference" / "ANSWER.txt").write_text(body)
    (HERE / "trap" / "ANSWER.txt").write_text("\n".join(trap) + "\n")
    print(f"answer: {len(full)} ids   trap: {len(trap)} ids   log: "
          f"{sum(1 for _ in open(HERE / 'workspace' / 'service.log'))} requests")
    for name, ids in decisions.items():
        print(f"  {name:22s} {len(ids)} id(s): {' '.join(sorted(ids))}")
    if show_table:
        checker.table(HERE / "workspace")


if __name__ == "__main__":
    main("--table" in sys.argv)
