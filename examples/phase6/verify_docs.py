"""Execute the worker-authored usage example against already public input."""
from pathlib import Path
import re
import shlex
import sys

sys.path.insert(0, str(Path("src").resolve()))
import click
from click.testing import CliRunner

text = Path("docs/parameter-types.md").read_text()
section = text[text.rfind("# ISODateTime"):]
examples = re.findall(r"```python\s*\n(.*?)\n```", section, re.DOTALL)
assert examples, "missing Python usage example"
count = 0
for example in examples:
    namespace = {"__name__": "public_documentation_example"}
    exec(compile(example, "<public-documentation-example>", "exec"), namespace)
    commands = [value for value in namespace.values() if isinstance(value, click.Command)]
    for command in commands:
        args = []
        for param in command.params:
            if isinstance(param.type, click.ISODateTime):
                if isinstance(param, click.Option):
                    args.append(param.opts[0])
                args.append("2024-01-01T12:00:00Z")
        assert args, "example does not use the new parameter type"
        result = CliRunner().invoke(command, args)
        assert result.exit_code == 0, result.output
        assert "2024-01-01" in result.output, "example must show the converted value"
        for transcript in re.findall(r"```bash\s*\n(.*?)\n```", section, re.DOTALL):
            lines = transcript.splitlines()
            if lines and lines[0].startswith("$ python ") and any(line.startswith("Error:") for line in lines[1:]):
                argv = shlex.split(lines[0][2:])[2:]
                failure = CliRunner().invoke(command, argv)
                assert failure.exit_code == 2, "documented rejection actually succeeds: " + repr(argv)
                assert "ISO 8601" in failure.output, failure.output
        count += 1
assert count, "example did not define an invocable command"
print(f"Documentation CLI examples passed: {count}")
