# Command-line interface

Install the package in a virtual environment, then run `cmne --help`.

| Command | Effect | Output |
|---|---|---|
| `cmne create PATH [--name NAME] [--sample]` | Create a new project; `--sample` seeds Mara and Len and C0–C3 | Project path |
| `cmne run PATH [--branch ID]` | Synchronously run a branch; default `main` | Pretty printed run JSON |
| `cmne graph PATH [--branch ID] [--lens LENS]` | Read a lens graph; defaults `main`, `story` | Pretty printed graph JSON |

```sh
source .venv/bin/activate
cmne create /tmp/cmne-example --sample
cmne run /tmp/cmne-example --branch main
cmne graph /tmp/cmne-example --branch main --lens story
```

Accepted lens names are `fixture`, `story`, `discourse`, `mind`, `provenance`, `motif`, and `pipeline`. For the sample comparison, inspect branch IDs in `project.cmne.json` or use the GUI/sidecar `branch.list`. The CLI does not expose export or draft editing; [JSON-RPC](json-rpc.md) does.
