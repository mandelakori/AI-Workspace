# Local OpenCode engineering smoke passed

The single authorized run at `e716250` passed on 2026-11-24. The exact local
grant `ce3bf3c489e129f05325084be56363f80411384ca9010d895df9a166a6eb6d45`
is consumed. The frozen runner exited zero in 149.042 seconds. There were no
retries, fallback profiles, configuration changes or implementation guidance.

| Gate or measurement | Result |
| --- | --- |
| Model initialization | One load-only request confirmed the pinned Qwen3.5 9B Q4_K_M model resident at 16,384 tokens in 47.407 s. |
| Reuse by OpenCode | One llama.cpp server start in the owned Ollama log. All four engineering requests returned HTTP 200 through that same owned instance. |
| Scoped edit | Two inspections followed by one accepted edit at operation 3. Only `units.py` changed. |
| Public checks | Worker public command passed at operation 4. The controller reran the suite and recorded 4/4. The pristine baseline was 1/4. |
| Independent acceptance | 6/6 after freeze, compared with a pristine 0/6. The independent suite stayed outside the worker workspace. |
| Model and MCP usage | 4/12 generation requests, 4/20 MCP operations and 0/1 compactions. All outgoing requests had thinking OFF and a 1,536-token output ceiling. |
| Verified provider usage | 16,044 prompt and 655 completion tokens, 16,699 total. The provider reported no separate reasoning count. All 12 capture files matched their recorded hashes and byte counts. |
| Timing | Work took 137.953 s including initialization and public verification. OpenCode took 78.219 s and provider requests totaled 68.826 s. Independent grading took 3.968 s. |
| Cleanup | Ollama, OpenCode relay and owned container cleanup passed. The loopback listener was closed after exit. The trial was not quarantined. |

The frozen model-authored edit changed the return expression to the standard
Fahrenheit-to-Celsius conversion and preserved the function signature. The
candidate SHA-256 is
`db1bdd7f631a2f1b9c9e632f0e57fb1854b234160670a85cea00a82569a31d7f`.
It is archived as a trial artifact. This run verifies the corrected local
initialization-to-verification path for one bounded fixture. Complex autonomous
engineering and stateful native reconstruction retain their documented limits.

[Execution evidence](evidence/local-engineering-smoke-result/evidence-hashes.json)
