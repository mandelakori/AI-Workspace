"""Offline wheel build/install and CLI integration against the public contract."""
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    wheels = root / "wheels"
    installed = root / "installed"
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                    "--no-index", "--no-cache-dir", "--wheel-dir", str(wheels), "."], check=True)
    wheel, = wheels.glob("*.whl")
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                    "--no-cache-dir", "--target", str(installed), str(wheel)], check=True)
    code = '''
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import click
from click.testing import CliRunner
assert Path(click.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
@click.command()
@click.option("--when", type=click.ISODateTime(normalize_to_utc=True))
def command(when):
    click.echo(when.isoformat())
runner = CliRunner()
result = runner.invoke(command, ["--when", "2024-01-01T01:00:00+05:30"])
assert result.exit_code == 0 and result.output == "2023-12-31T19:30:00+00:00\\n", result.output
result = runner.invoke(command, ["--when", "yesterday"])
assert result.exit_code == 2 and "ISO 8601" in result.output, result.output
print("Installed wheel CLI integration passed")
'''
    subprocess.run([sys.executable, "-I", "-c", code, str(installed)], check=True)
