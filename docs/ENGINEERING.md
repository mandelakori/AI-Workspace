# Engineering mode

Phase 2 keeps the restricted manifest contract as the default. A job opts into engineering with `mode = "engineering"` and explicit `write_roots`. A root can name an exact file, a directory, or a path that will be created. Read access covers the staged inputs. Keep credentials and secrets out of those inputs.

## Install the runner and submit work

The sample configuration uses a separate queue and shares hardware locks with the original queue. It uses the existing OpenCode and `aisak` setup.
Refresh the installed CLI with `scripts/Bootstrap.ps1` during an idle window. For an immediate source-tree run, replace `& $ai` below with `& .\.venv\Scripts\python.exe -m aiwork`.

```powershell
docker desktop start
docker pull python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
$ai = '.\.venv\Scripts\aiwork.exe'
$cfg = 'config/engineering.example.toml'
& $ai --config $cfg doctor
& $ai --config $cfg task run examples/phase2/feature.toml --profile a100-existing
& $ai --config $cfg task run examples/phase2/debug.toml --profile a100-existing
& $ai --config $cfg plan examples/phase2/objective.toml --id parcel-release --min-steps 2 --max-steps 2 --cover-commands
& $ai --config $cfg plan examples/phase2/collaboration.toml --id sensor-release-demo --min-steps 2 --max-steps 2 --cover-commands
```

Use `--plan-only` to generate and review a plan before starting its jobs. Rerun the same manifest and ID with the same step limit to continue. The graph is saved in `.aiwork/phase2/plans/<id>/plan.json`. Its journal identifies assigned profiles, verified jobs, the integrated tree, and the combined patch. [Docker Desktop CLI](https://docs.docker.com/desktop/features/desktop-cli/)

Use `scripts/Controller.ps1 -Action Start -Config config/engineering.example.toml` to serve the Phase 2 queue in the background.

## Write a project manifest

Set `workspace`, a concrete `objective`, and a category. Narrow `inputs` for large repositories. Source staging is bounded to 5,000 files and 64 MiB. Intake records hashes and project metadata. The harness receives a relevance index and opens selected files as needed.

- Use `[[commands]]` for public recipes the agent may run by index. Each entry runs an exact argument array and can set a workspace-relative `cwd`, a timeout and expected stdout. To reproduce a bug before the agent starts, set `baseline_check = true` and put the failing reproduction at index 0.
- Use `[[setup]]` for reviewed prerequisites. For example, stage a wheel in the input tree, install it with `python -m pip install --no-index --no-deps --target .deps wheelhouse/package.whl`, and make the approved checks load that local directory. Each public invocation rebuilds setup in a disposable copy. Independent verification runs setup once in its own copy.
- Use `[[checks]]` for independent commands that decide final acceptance. Existing build, lint, unit and integration tools can run here. Test discovery hints from intake do not add commands to the approved list.
- Put private tests in a separate `verification_dir` and refer to it using `{verification}` only in independent checks. Agent tool calls and diagnostic prompts never receive the private files or their output. For hostile candidates use a separate evaluator identity and a test protocol that does not expose oracle material to candidate code.
- Set `min_context` when a task needs a profile with a larger serving context. Engineering mode currently uses OpenCode. Qwen Code still supports the original restricted mode.

Recipes run with the named Docker image, a private staged workspace, networking disabled and caps on CPU, memory and processes. Only reviewed workflows can use the host fallback. Choose a config with no `verification_image` and pass `--trusted` for that specific task. Both modes keep the model's native shell disabled.

## Check and integrate a proposal

```powershell
& $ai --config $cfg patch <job-id> --check 'C:\path\to\source'
& $ai --config $cfg patch parcel-release --plan --check 'C:\path\to\source'
```

This checks the saved patch hash and optionally runs `git apply --check` against a checkout. Review the patch and evidence, then apply it on a review branch using `git -c core.autocrlf=false apply <patch>`. An engineering job that fails can be resumed from its latest validated in-scope checkpoint, or restarted from its frozen source with `task resume <job-id> --reset`. An abandoned `running` job can be requeued with `--interrupted` once its worker exits. A plan can continue after requeuing one of its child jobs.

## Propose an AI Workspace improvement

Build a Git-equipped runner for the isolated project regression suite:

```powershell
docker build -t aiwork-engineering:phase2 -f config/engineering.Dockerfile config
(Get-Content -Raw $cfg).Replace(
    'python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b',
    'aiwork-engineering:phase2'
) | Set-Content -Encoding utf8NoBOM config/self.local.toml
& $ai --config config/self.local.toml self --repo . --profile a100-existing
```

The self workflow archives committed Git HEAD and records its hash. Its write policy permits an index change and a targeted regression test. Check the resulting patch with `patch <job-id> --check .` before deciding whether to integrate it.
