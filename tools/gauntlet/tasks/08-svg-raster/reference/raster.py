"""Rasterize a filled SVG path (reference)."""
import re

_TOK = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _subpaths(d):
    toks = _TOK.findall(d)
    if re.sub(r"[\s,]", "", d) != "".join(toks):
        raise ValueError("unparseable path")
    subs, cur, start, pt, cmd, i = [], None, (0.0, 0.0), (0.0, 0.0), None, 0

    def num():
        nonlocal i
        if i >= len(toks) or toks[i].isalpha():
            raise ValueError("missing number")
        i += 1
        return float(toks[i - 1])

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if cur is not None:
                    subs.append(cur)
                    cur = None
                pt = start
                continue
        elif cmd is None or cmd in "Zz":
            raise ValueError("number without a command")
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            x, y = num(), num()
            pt = (pt[0] + x, pt[1] + y) if rel else (x, y)
            if cur is not None:
                subs.append(cur)
            cur, start = [pt], pt
            cmd = "l" if rel else "L"
        elif c == "L":
            x, y = num(), num()
            pt = (pt[0] + x, pt[1] + y) if rel else (x, y)
            cur = cur if cur is not None else [start]
            cur.append(pt)
        elif c == "H":
            x = num()
            pt = (pt[0] + x if rel else x, pt[1])
            cur = cur if cur is not None else [start]
            cur.append(pt)
        elif c == "V":
            y = num()
            pt = (pt[0], pt[1] + y if rel else y)
            cur = cur if cur is not None else [start]
            cur.append(pt)
        else:
            raise ValueError(f"unknown command {cmd}")
    if cur is not None:
        subs.append(cur)
    return subs


def rasterize(d, width, height, fill_rule="nonzero"):
    if fill_rule not in ("nonzero", "evenodd"):
        raise ValueError("fill_rule")
    edges = []
    for poly in _subpaths(d):
        for k in range(len(poly)):
            a, b = poly[k], poly[(k + 1) % len(poly)]
            if a[1] != b[1]:
                edges.append((a[0], a[1], b[0], b[1]))
    out = []
    for row in range(height):
        cy = row + 0.5
        line = []
        for col in range(width):
            cx = col + 0.5
            wind, cross = 0, 0
            for x0, y0, x1, y1 in edges:
                if (y0 <= cy < y1) or (y1 <= cy < y0):
                    xc = x0 + (cy - y0) * (x1 - x0) / (y1 - y0)
                    if xc > cx:
                        cross += 1
                        wind += 1 if y1 > y0 else -1
            inside = wind != 0 if fill_rule == "nonzero" else cross % 2 == 1
            line.append("#" if inside else ".")
        out.append("".join(line))
    return out
