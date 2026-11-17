"""Operator-side generator. Keep its output outside worker workspaces."""
import argparse
import json
import random
import string
from pathlib import Path


def ledger(rng):
    def value(amount):
        return f"add {amount}\nshow\ntake 2\nshow\n"

    for amount in (-1, 0, 1, 999, 1000, 1001):
        yield "boundary", {"stdin": value(amount)}
    yield "boundary", {"stdin": "add 1000\n" * 10 + "add 1\nshow\ntake 1000\n"}
    yield "malformed", {"stdin": "show extra\nreset extra\nadd 2 extra\nadd\n\nshow"}
    for _ in range(40):
        commands = [rng.choice(("show", "reset", "bad", f"add {rng.randrange(-2, 1004)}",
                                f"take {rng.randrange(-2, 1004)}")) for _ in range(25)]
        yield "stateful-random", {"stdin": "\n".join(commands) + "\n"}


def bucket(rng):
    for x in (-21, -20, -19, -1, 1, 9, 10, 11, 39, 40, 41, 79, 80, 81, -(2**31), 2**31-1):
        yield "boundary", {"stdin": f"{x}\n"}
    for value in ("", " ", " +00080 \n", "2 3\n", "3.5\n", "3x\n", "--2\n", "\n-09"):
        yield "parsing", {"stdin": value}
    for x in rng.sample(range(-10000, -100), 12) + rng.sample(range(100, 10000), 12):
        yield "random", {"stdin": f"{x}\n"}


def stride(rng):
    for length in (39, 40, 41):
        for step in ("1", "8", "9"):
            yield "boundary", {"argv": ["x" * length, step]}
    for step in ("", "0", "-1", "+02", " 2", "2 ", "2junk", "999999999999999999999999"):
        yield "parsing", {"argv": ["abc def", step]}
    yield "arity", {"argv": ["one"]}
    yield "arity", {"argv": ["too", "2", "many"]}
    yield "literal", {"argv": ["{python}", "1"]}
    for _ in range(28):
        word = "".join(rng.choices(string.ascii_letters + " :_", k=rng.randrange(5, 43)))
        yield "random", {"argv": [word, str(rng.randrange(1, 9))]}


def main():
    generators = {"ledger": ledger, "bucket": bucket, "stride": stride}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=generators)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    rows = [{"name": f"{args.target}-{index:03}", "group": group, **data}
            for index, (group, data) in enumerate(generators[args.target](random.Random(args.seed)), 1)]
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(rows, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
