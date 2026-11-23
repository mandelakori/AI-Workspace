# One final Milestone E acceptance trial

Preparation is not authorization. FEATURE.md and the original twelve public cases
are byte-identical to the prior frozen specification. PUBLIC-VERIFICATION.md
clarifies executable development gates without providing an implementation.
The new corpus adds 36 public behavior cases; combined behavior is scored /48.
Authored tests, upstream, interfaces/docstrings, documentation and syntax are
separate mandatory gates. Prior solutions/diagnostic drivers are not worker inputs.

Use the existing virtual environment, pinned clean ItsDangerous commit and offline
image. No model download or service change is required. Read the current operator
review in docs/MILESTONE-E-FINAL-REVIEW.md for the bundle and exact digest.

```powershell
.\.venv\Scripts\python.exe examples/milestone-e-final/trial.py validate .aiwork/milestone-e-final/acceptance-trial
# Only after separate exact approval:
# .\.venv\Scripts\python.exe examples/milestone-e-final/trial.py run .aiwork/milestone-e-final/acceptance-trial --approval <approval.json>
```

One A100/OpenCode attempt only: 65536 context, 4096 output tokens, temperature 0,
seed 1729, reasoning disabled; 720-second attempt, 96 MCP calls (8 edit/8 test
reservations), 64 model requests, four compactions; 20/900/120 phase reservations.
Capture policy is the verified 64 MiB payload/32 MiB headroom implementation.
Permitted write paths and scope remain unchanged. No planner, retries, fallback,
historical candidate reuse or mid-run implementation guidance.

An incomplete but clean attempt is retained with engineering-incomplete.json,
never frozen or graded. Provider/cleanup/interruption failures quarantine. Only
all public gates, clean completed worker execution, model edits and a successful
worker acceptance call permit a frozen candidate. Independent grading requires
24 genuinely new cases authored after that freeze; controller-only semantic
exclusions reject public/previous diagnostic inputs, cosmetic ID changes and
duplicates. No sealed cases exist during preparation.

After this one authorized execution, stop and assess whether the existing
model/harness met Milestone E. Never automatically repeat ItsDangerous.
