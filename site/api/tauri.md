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

The Rust bridge permits only methods in its `METHODS` allow-list, currently the [JSON-RPC reference](json-rpc.md) method set. It owns one child sidecar behind a mutex, increments request IDs, checks matching response IDs, and performs the protocol handshake on start. Development uses `python3 -m cmne_sidecar.server` with `PYTHONPATH` set to the repository `src`; the packaged app uses its bundled `cmne-sidecar` executable. `CMNE_SIDECAR_BIN` can override the child path. After an unexpected exit or broken pipe, the bridge starts a new child and retries the call once; clients may need to reopen the project because sidecar state is process-local.

The shell does not interpret narrative payloads. Validation and storage stay in the Python kernel. A single synchronous run blocks the sidecar request until it returns; `run.cancel` is currently a no-op response.
