# PyPA benchmark exposure review

The affected execution is A100 OpenCode job `ffde5b150ada4309b1f1ee6dbb2df40e`, attempt 1, in benchmark `d450ad15a53a49ec92bf1837175c201f`. The saved `agent.jsonl` contains 496 records and has SHA-256 `b72fe1b54060461cba69026fba1296e722aecc7bf709062a633a446091b5982a`. Its stderr file is empty. Attempt 2 has no saved harness trace. This review used saved evidence and did not resume either attempt.

## Successful content reads

Paths below are relative to the AI-Workspace checkout unless a different root is specified. Repeated reads are grouped.

| Root | Files |
| --- | --- |
| AI-Workspace checkout | `pyproject.toml`, `AGENTS.md`, `docs/NEXT_STEPS.md`, `docs/ENGINEERING.md`, `.git/config`, `aiwork.local.toml`, `examples/phase4/packaging.toml`, `examples/phase4/packaging_inputs.py` |
| `.aiwork/phase4/upstream-packaging` | `pyproject.toml`, `src/packaging/__init__.py`, `src/packaging/markers.py`, `src/packaging/requirements.py`, `src/packaging/specifiers.py`, `src/packaging/utils.py`, `src/packaging/version.py`, `tests/test_requirements.py` |
| Attempt 1 workspace, paths reported relative to the tool working directory | `tests/__init__.py`, `tests/test_requirement_policy.py` |

The worker also listed three directories through the read tool. These were `.git`, the upstream `src/packaging`, and the attempt workspace's `src/packaging`. Successful glob calls exposed path names from the checkout and staged project. Grep returned a snippet from `examples/phase4/packaging_inputs.py` and one from `examples/phase4/packaging.toml`; the search against `aiwork.local.toml` returned no match. Five read attempts failed and returned no content.

## Credentials and benchmark disposition

The saved `.git/config` contained an origin URL without embedded user information or a query. The saved `aiwork.local.toml` contained endpoint configuration without URL credentials or populated credential fields. A scan for private keys, bearer tokens, common provider tokens, JWTs and credential-like assignments found no live secret. The URL with embedded user information in the saved trace was verified against the pinned upstream `tests/test_requirements.py` blob and uses a reserved example domain. The saved evidence identifies no credential requiring rotation.

The worker read the case generator and wrote a test containing a sealed input. The affected benchmark and its checkpoint repair are excluded from independent evidence. The operator-assisted PyPA run `6ef1d9da4f1c46aaade89237a5d9306a` reused 14 of the contaminated run's 18 normalized inputs. Its entire 18-case generator-derived suite is classified as regression evidence, including the four inputs produced with a different seed. All suites and reports are retained as historical artifacts. Future independent PyPA evaluation requires a separately authored suite.

The installed OpenCode workspace-boundary test passed again. It used a scripted loopback model and verified denial of outside reads and searches, with a successful edit inside the staged workspace.
