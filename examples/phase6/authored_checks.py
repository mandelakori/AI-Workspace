"""Public review gates for requirements missed by the initial worker artifacts."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path("src").resolve()))

if sys.argv[1] == "cli":
    import pytest
    from click.testing import CliRunner
    original = CliRunner.invoke
    calls = []

    def counted(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    CliRunner.invoke = counted
    result = pytest.main(["-q", "-p", "no:cacheprovider", "tests/test_iso_datetime.py"])
    assert result == 0 and calls, "feature tests must actually invoke a command with CliRunner"
elif sys.argv[1] == "docs":
    types = Path("docs/parameter-types.md").read_text()
    api = Path("docs/api.md").read_text()
    section = types[types.rfind("# ISODateTime"):]
    assert re.search(r"\bDateTime\b", section), "explain compatibility with legacy DateTime"
    assert "click.option" in section and "```" in section, "provide an executable-style CLI usage example"
    assert ":module:" not in api, "autoclass has no module option; follow the existing currentmodule directive"
    assert "require_timezone" in section and "normalize_to_utc" in section
else:
    raise ValueError("unknown public review gate")
