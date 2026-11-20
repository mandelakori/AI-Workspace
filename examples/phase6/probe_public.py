"""Public black-box acceptance driver; contains no feature implementation."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path("src").resolve()))
import click
from click.testing import CliRunner


def evaluate(case):
    cls = getattr(click, "ISODateTime", None)
    if cls is None:
        return {"missing": "ISODateTime"}
    kind = case["kind"]
    flags = case.get("flags", {})
    converter = cls(**flags)
    if kind == "metadata":
        info = converter.to_info_dict()
        return {"export": click.types.ISODateTime is cls, "param_type": isinstance(converter, click.ParamType),
                "name": converter.name, "repr": repr(converter), "require_timezone": info.get("require_timezone"),
                "normalize_to_utc": info.get("normalize_to_utc")}
    if kind in {"parse", "identity"}:
        value = case.get("value")
        if kind == "identity":
            value = datetime(2024, 2, 29, 3, 4, 5, tzinfo=timezone(timedelta(hours=2)))
        try:
            result = converter.convert(value, None, None)
            return {"iso": result.isoformat(), **({"identity": result is value} if kind == "identity" else {})}
        except click.BadParameter as error:
            text = str(error).lower()
            return {"error": "BadParameter", "iso_hint": "iso 8601" in text,
                    **({"timezone_hint": "timezone" in text} if case.get("timezone_error") else {})}
    if kind == "legacy":
        try:
            result = click.DateTime().convert(case["value"], None, None)
            return {"iso": result.isoformat()}
        except click.BadParameter:
            return {"error": "BadParameter"}
    if kind == "repository":
        docs = Path("docs/parameter-types.md").read_text()+Path("docs/api.md").read_text()
        target = Path("tests/test_iso_datetime.py")
        if not target.exists():
            return {"complete": False}
        collected = subprocess.run([sys.executable, "-m", "pytest", "-q", "--collect-only", "-p", "no:cacheprovider", str(target)],
                                   capture_output=True, text=True, timeout=30)
        count = sum(line.startswith("tests/test_iso_datetime.py::") for line in collected.stdout.splitlines())
        completed = subprocess.run([sys.executable, "_aiwork_verify.py", "feature"], capture_output=True, timeout=45)
        return {"complete": count >= 6 and "ISODateTime" in docs and "require_timezone" in docs
                and "normalize_to_utc" in docs and completed.returncode == 0}
    if kind == "cli":
        @click.command()
        @click.option("--when", type=converter, multiple=case.get("multiple", False),
                      envvar="WHEN_VALUE", default=case.get("default"))
        def command(when):
            values = when if case.get("multiple") else (when,)
            click.echo("|".join(value.isoformat() for value in values))
        result = CliRunner().invoke(command, case.get("args", []), env=case.get("env", {}))
        if case.get("help"):
            return {"code": result.exit_code, "metavar": "ISO_DATETIME" in result.output}
        if case.get("error"):
            return {"code": result.exit_code, "parameter_hint": "Invalid value for '--when'" in result.output,
                    "iso_hint": "iso 8601" in result.output.lower()}
        return {"code": result.exit_code, "output": result.output}
    raise ValueError("unknown public probe")


if __name__ == "__main__":
    print(json.dumps(evaluate(json.load(sys.stdin)), sort_keys=True, separators=(",", ":")))
