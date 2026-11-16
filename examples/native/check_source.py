"""Preflight the deliberately tiny source language of the native demonstration."""
import re
from pathlib import Path

template = Path(__file__).with_name("candidate-template.c").read_text(encoding="utf-8")
source = Path("candidate.c").read_text(encoding="utf-8")
signature = "int shipping_points(int weight, int priority) {"
prefix, tail = template.split(signature, 1)
suffix = tail[tail.index("\n}\n"):]
prefix += signature
if not source.startswith(prefix) or not source.endswith(suffix):
    raise SystemExit("Only the body of shipping_points may be changed")
body = source[len(prefix):-len(suffix)]
if not 1 <= len(body) <= 1400 or re.search(r"\bint\s*\*|\+\+|--", body):
    raise SystemExit("Body exceeds the toy source policy")
token = re.compile(r"\s+|[A-Za-z_]\w*|[0-9]+|[+*\-(){}<>=!;?:]")
allowed = {"weight", "priority", "points", "result", "int", "if", "else", "return"}
position = 0
while position < len(body):
    match = token.match(body, position)
    if not match:
        raise SystemExit("Disallowed syntax in toy function")
    item = match.group()
    if item[0].isalpha() or item[0] == "_":
        if item not in allowed:
            raise SystemExit("Disallowed identifier in toy function")
    elif item.isdigit() and int(item) > 1000:
        raise SystemExit("Literal too large for toy function")
    position = match.end()
