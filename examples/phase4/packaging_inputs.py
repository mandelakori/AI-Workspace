"""Generate an operator-only oracle for the packaging feature benchmark."""
import argparse
import json
import random
from pathlib import Path


def expected(requirement, name, status, version=None):
    return dict(requirement=requirement, name=name, status=status, version=version)


def success(requirements, installed, results, **options):
    return {
        "stdin": json.dumps(dict(requirements=requirements, installed=installed, **options)),
        "stdout": json.dumps({"results": results}, sort_keys=True, separators=(",", ":")) + "\n",
        "stderr": "",
        "code": 0,
    }


def invalid(payload):
    return {"stdin": payload, "stdout": "", "stderr": "invalid policy input\n", "code": 2}


def cases(seed):
    yield success(["  Zed==4  ", "# ignored", " ", "FOO_Bar>3", "Foo.Bar<3", "Zed==3"],
                  {"foo-bar": "4.0", "zed": "4"},
                  [expected("FOO_Bar>3", "foo-bar", "satisfied", "4.0"),
                   expected("Foo.Bar<3", "foo-bar", "incompatible", "4.0"),
                   expected("Zed==4", "zed", "satisfied", "4"),
                   expected("Zed==3", "zed", "incompatible", "4")])
    yes = 'Beta>=2; python_version < "4"'
    no = 'Alpha; python_version < "3"'
    yield success([yes, no], {"alpha": "1", "beta": "2"}, [
        expected(no, "alpha", "skipped"), expected(yes, "beta", "satisfied", "2")],
        environment={"python_version": "3.10"})
    yield success(["Lib[optional]>=2.0rc1", " absent ", "Lib<2"],
                  {"LIB": "2.0rc2"}, [expected("absent", "absent", "missing"),
                      expected("Lib[optional]>=2.0rc1", "lib", "satisfied", "2.0rc2"),
                      expected("Lib<2", "lib", "incompatible", "2.0rc2")])
    for requirements, installed in [
        (["dep @ https://example.invalid/pkg.whl"], {}),
        (["bad!"], {}), (["name"], {"A_B": "1", "a-b": "2"}),
        (["name"], {"name": "nonsense"}), (["name"], {"name": 1}),
        ([1], {}), ("name", {}), ([], []),
    ]:
        yield invalid(json.dumps(dict(requirements=requirements, installed=installed)))
    yield invalid("{bad json")
    yield invalid(json.dumps({"requirements": [], "installed": {}, "environment": ["linux"]}))
    yield success([], {}, [])
    rng = random.Random(seed)
    for _ in range(4):
        high = rng.randrange(40, 100)
        low = rng.randrange(1, 20)
        constraints = [f"X.Y<{high}", f"c_pkg>{high}", f"x-y>{high}", f"X_Y>={low}", "a-other"]
        rng.shuffle(constraints)
        results = [expected(rule, "x-y", "incompatible" if ">" in rule and str(high) in rule
                            else "satisfied", str(low)) for rule in constraints if rule[:1].lower() == "x"]
        yield success(constraints, {"x_y": str(low), "C-Pkg": str(low)},
                      [expected("a-other", "a-other", "missing"),
                       expected(f"c_pkg>{high}", "c-pkg", "incompatible", str(low)), *results])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(list(cases(args.seed)), output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
