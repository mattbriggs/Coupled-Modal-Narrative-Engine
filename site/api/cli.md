# Command-line interface

Install the package in a virtual environment, then run `cmne --help`. Add `--json` **before** the command for machine-readable success and error objects. Success exits 0; a domain or input error exits 2 and includes a code, cause, field path, and corrective action.

| Command | Effect |
|---|---|
| `create PATH [--name NAME] [--sample]` | Create a project and optional Mara/Len sample |
| `validate-contract FILE` | Validate a JSON narrative contract |
| `replay PATH [--branch ID]` | Replay six projections and hashes |
| `fork PATH SEQUENCE NAME [--branch ID]` | Create an independent branch and draft suffix |
| `apply-revision PATH C0\|C1\|C2\|C3` | Inspect a seeded condition's revision state |
| `plan-discourse PATH FILE [--branch ID]` | Atomically seal an `acts` array from JSON |
| `packet PATH [--branch ID]` | Build a filtered scene packet |
| `realize PATH [--branch ID] [--variant 0\|1\|2]` | Realize and check deterministic prose |
| `check PATH FILE [--branch ID]` | Check a UTF-8 prose file against the packet |
| `trace PATH TARGET [--query TYPE]` | Trace an event, actor belief, reader inference, model change, or run exposure |
| `run PATH [--branch ID] [--variant 0\|1\|2]` | Save a run and rejected-candidate findings |
| `propose PATH [--branch ID] --model-manifest FILE` | Save diagnostic model proposals outside canon |
| `accept-proposal PATH PROPOSAL_ID [--branch ID]` | Validate and seal a stored proposal |
| `graph PATH [--branch ID] [--lens LENS]` | Read a lens graph |
| `analysis-plan PATH FILE` | Save or amend the fixed study plan |
| `study-generate PATH` | Save three matched template variants for C0–C3 |
| `study-metrics PATH [--branch ID]` | Read blocking and descriptive structural measures |
| `study-ablations PATH [--branch ID]` | Read seven analysis-only ablation descriptions |
| `study-realize-ablations PATH [--branch ID]` | Save seven controlled ablation passages and checker findings |
| `export-evaluation PATH [--seed N]` | Write randomized public passages and a separate private key |
| `responses-import PATH STUDY_ID FILE` | Atomically validate and import evaluator responses |
| `report PATH STUDY_ID` | Save and print a descriptive study report |
| `decision-packet PATH STUDY_ID` | Save a hashed review packet with study, structural, and ablation evidence |

Example:

```sh
source .venv/bin/activate
cmne create /tmp/cmne-example --sample
cmne --json replay /tmp/cmne-example
cmne study-generate /tmp/cmne-example
cmne analysis-plan /tmp/cmne-example plan.json
cmne export-evaluation /tmp/cmne-example --seed 33
```

`analysis-plan` must precede export. The CLI accepts only JSON imports; it does not execute YAML tags. See [Prepare a blinded evaluation](../manual/evaluate-study.md) for the plan and response fields. Long CLI runs are synchronous; the desktop sidecar offers background run polling and cancellation between conditions.

`run` and `propose` also accept `--adapter-mode record|replay`, `--adapter-command EXECUTABLE`, `--model-manifest FILE`, `--max-calls`, `--max-tokens`, optional `--max-cost-micros`, and `--allow-data-transfer`. The default `run` mode remains `template`. The [model adapter contract](model-adapters.md) explains the JSON protocol, privacy gate, cassette, and budget behavior.
