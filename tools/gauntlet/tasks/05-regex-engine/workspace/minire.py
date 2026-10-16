"""A small regular-expression engine.  Implement fullmatch(pattern, text) -> bool.

Syntax (a subset of Python's `re`, same meaning):
  c          a literal character (anything not special below)
  .          any single character (including newline)
  [abc] [a-z0-9] [^abc]   a character class; ranges; leading ^ negates; inside a class only `]`, `\\`, `^` (first)
             and `-` (between two chars) are special; `\\]` `\\\\` `\\-` `\\^` are escapes there
  \\x         escape: the next character literally (e.g. \\. \\* \\( \\| \\[ \\\\)
  X* X+ X?   zero-or-more / one-or-more / zero-or-one of the preceding atom (a literal, ., a class or a group)
  ( ... )    group (no capturing needed)
  A|B        alternation, lowest precedence; an empty branch matches the empty string ("a|" matches "" and "a")
The whole text must match (like re.fullmatch).  An empty pattern matches only the empty text.
Malformed patterns ("(", "a)", "*a", "[a", "a**" is NOT malformed - but you will not be tested on doubled quantifiers)
raise ValueError.

PERFORMANCE IS PART OF THE SPEC: matching must take polynomial time in len(pattern) * len(text) - e.g.
fullmatch("(a*)*b", "a" * 40) and fullmatch("(a|aa)*c", "a" * 60) must each return False in well under a second.
"""


def fullmatch(pattern, text):
    raise NotImplementedError
