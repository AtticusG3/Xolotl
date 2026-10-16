"""A small regular-expression engine (reference: parse -> Thompson NFA -> set simulation, O(len(p) * len(t)))."""


class _P:
    def __init__(self, p):
        self.p, self.i = p, 0

    def peek(self):
        return self.p[self.i] if self.i < len(self.p) else None

    def take(self):
        c = self.p[self.i]
        self.i += 1
        return c

    def alt(self):
        branches = [self.concat()]
        while self.peek() == "|":
            self.take()
            branches.append(self.concat())
        return ("alt", branches) if len(branches) > 1 else branches[0]

    def concat(self):
        items = []
        while self.peek() is not None and self.peek() not in "|)":
            items.append(self.repeat())
        return ("cat", items)

    def repeat(self):
        a = self.atom()
        while self.peek() is not None and self.peek() in "*+?":
            a = (self.take(), a)
        return a

    def atom(self):
        c = self.take()
        if c == "(":
            inner = self.alt()
            if self.peek() != ")":
                raise ValueError("missing )")
            self.take()
            return inner
        if c in "*+?":
            raise ValueError("nothing to repeat")
        if c == ")":
            raise ValueError("unbalanced )")
        if c == ".":
            return ("any",)
        if c == "\\":
            if self.peek() is None:
                raise ValueError("trailing backslash")
            return ("lit", self.take())
        if c == "[":
            return self.cls()
        return ("lit", c)

    def cls(self):
        neg = False
        if self.peek() == "^":
            self.take()
            neg = True
        items, first = [], True
        while True:
            c = self.peek()
            if c is None:
                raise ValueError("missing ]")
            if c == "]" and not first:
                self.take()
                break
            c = self.take()
            if c == "\\":
                if self.peek() is None:
                    raise ValueError("trailing backslash")
                c = self.take()
            if self.peek() == "-" and self.i + 1 < len(self.p) and self.p[self.i + 1] != "]":
                self.take()
                hi = self.take()
                if hi == "\\":
                    hi = self.take()
                if hi < c:
                    raise ValueError("bad range")
                items.append((c, hi))
            else:
                items.append((c, c))
            first = False
        return ("cls", neg, items)


def _compile(node, nfa):
    """Thompson construction; returns (start, accept) state ids.  nfa: list of [kind, data, out1, out2]."""
    def new(kind=None, data=None):
        nfa.append([kind, data, None, None])
        return len(nfa) - 1
    k = node[0]
    if k in ("lit", "any", "cls"):
        s, e = new("char", node), new()
        nfa[s][2] = e
        return s, e
    if k == "cat":
        if not node[1]:
            s = new()
            return s, s
        s, e = _compile(node[1][0], nfa)
        for sub in node[1][1:]:
            s2, e2 = _compile(sub, nfa)
            nfa[e][2] = s2
            e = e2
        return s, e
    if k == "alt":
        s, e = new(), new()
        outs = []
        for b in node[1]:
            bs, be = _compile(b, nfa)
            outs.append(bs)
            nfa[be][2] = e
        nfa[s][0], nfa[s][1] = "split", outs
        return s, e
    q, sub = k, node[1]
    bs, be = _compile(sub, nfa)
    s, e = new(), new()
    if q == "*":
        nfa[s][0], nfa[s][1] = "split", [bs, e]
        nfa[be][0], nfa[be][1] = "split", [bs, e]
    elif q == "+":
        nfa[s][2] = bs
        nfa[be][0], nfa[be][1] = "split", [bs, e]
    else:
        nfa[s][0], nfa[s][1] = "split", [bs, e]
        nfa[be][2] = e
    return s, e


def _match_char(node, c):
    if node[0] == "any":
        return True
    if node[0] == "lit":
        return node[1] == c
    hit = any(lo <= c <= hi for lo, hi in node[2])
    return hit != node[1]


def fullmatch(pattern, text):
    p = _P(pattern)
    ast = p.alt()
    if p.i != len(pattern):
        raise ValueError("unbalanced )")
    nfa = []
    start, accept = _compile(ast, nfa)

    def closure(states):
        seen, stack = set(), list(states)
        while stack:
            s = stack.pop()
            if s is None or s in seen:
                continue
            seen.add(s)
            kind = nfa[s][0]
            if kind == "split":
                stack.extend(nfa[s][1])
            elif kind is None:
                stack.append(nfa[s][2])
        return seen

    cur = closure([start])
    for c in text:
        nxt = [nfa[s][2] for s in cur if nfa[s][0] == "char" and _match_char(nfa[s][1], c)]
        cur = closure(nxt)
        if not cur:
            return False
    return accept in cur
