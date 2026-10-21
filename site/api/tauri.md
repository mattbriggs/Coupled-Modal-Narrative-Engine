# Tauri bridge

The Rust shell exposes two commands to the React frontend:

| Command | Arguments | Result |
|---|---|---|
| `rpc_call` | `method: string`, `params: JSON object` | Sidecar `result` value or rejected promise with error string |
| `default_sample_path` | None | Documents/CMNE/Mara and Len path |

```ts
import { invoke } from "@tauri-apps/api/core";

const project = await invoke("rpc_call", {
  method: "project.sample",
  params: {},
});
const path = await invoke<string>("default_sample_path");
```

`app/src/api.ts` wraps `invoke` in `rpc<T>(method, params)` and turns serialized sidecar errors into messages containing the CMNE code and field path. It also defines `Lens`, `ViewNode`, `ViewEdge`, `ViewGraph`, `Draft`, `ProjectSummary`, and `RunResult` TypeScript types.

The Rust bridge permits only methods in its `METHODS` allow-list, currently the [JSON-RPC reference](json-rpc.md) method set. It owns one child sidecar behind a mutex, increments request IDs, checks matching response IDs, and performs the protocol handshake on start. Development uses `python3 -m cmne_sidecar.server` with `PYTHONPATH` set to the repository `src`; the packaged app uses its bundled `cmne-sidecar` executable. `CMNE_SIDECAR_BIN` can override the child path. After an unexpected exit or broken pipe, the bridge retries only stateless `app.hello`, `fixture.validate`, and `contract.validate` calls. It returns an uncertain-outcome error for project calls and creates a fresh sidecar on the next request. Reopen and inspect the project before repeating an interrupted mutation; the bridge cannot infer whether that mutation committed before the child stopped.

The shell does not interpret narrative payloads. Validation and storage stay in the Python kernel. The workbench calls `run.start` with `async: true`, polls `run.status`, and can request `run.cancel`; the sidecar stops before the next condition. The Rust bridge still serializes individual RPC requests, but each background-run request returns promptly so committed-state reads remain available.
