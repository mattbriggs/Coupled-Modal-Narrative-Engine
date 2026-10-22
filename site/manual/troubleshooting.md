# Recovery and troubleshooting — S-10, S-13

## Procedure — a run failed

1. Read the finding code and message in the run view or saved `runs/<run-id>.json`.
2. For `E-RUN-EMPTY`, seal a story event. For `E-RUN-PLAN`, seal a discourse act that references story.
3. For `E-RUN-CONTRACT`, add the required world fact to a story event, or correct the contract if the requirement was wrong.
4. For `E-PROSE-WORDS`, edit the discourse text or the contract bounds. For `E-PROSE-FORBIDDEN`, revise the authored text and run again.
5. If the correction changes a sealed event, fork before editing. Export the new run after it passes.

## Procedure — a draft did not seal

1. Keep the draft open and run its preview validation.
2. Follow the error's `field_path`: check title, actor IDs, story references, causal edges, observation access, and disclosure grounding.
3. Correct the draft and preview again. A rejected seal returns errors and does not emit events.
4. Seal after preview accepts it. Draft JSON persists in `<project>/drafts/` until sealed or deleted; after an interrupted session, reopen the project and inspect the recovered draft. The workbench can find the newest draft for the branch and lens on disk even if its local-storage pointer was lost.

## Principle — preserve project integrity

Do not hand edit sealed NDJSON streams. The engine verifies event IDs, hashes, sequence, and schema when reading them. A second writer receives `E-LOCK-001`; close the first app/process before reopening the project. Back up the whole project directory when sharing or archiving a branch.

If the app reports a **stale lock**, confirm the former writer has stopped, then clear it through `project.clear_stale_lock` or `Project.clear_stale_lock(path)` before reopening. A read-only open can inspect committed history while another process owns the writer lock. Never clear a lock for a running process or another host.

## Procedure — sidecar stopped during a project operation

1. Read the error. An **outcome unknown** message means the child stopped before the shell could confirm whether the operation committed.
2. Reopen the project. If its old writer left a stale lock, confirm the child stopped and clear that lock explicitly.
3. Read the relevant event stream, draft, contract, or run record before repeating the action. A failed project switch keeps the previous open project; a failed contract edit leaves its old bytes intact.
4. Repeat only work that is absent from the saved project. The shell automatically retries only stateless validation calls.

## Fact — current recovery scope

Saved drafts and sealed streams survive a normal process interruption. The optional [JSON adapter](../api/model-adapters.md) records failure without vendor exception text and falls back to the template on an unavailable prose adapter. Its call, token, and optional cost limits stop additional calls with `E-BUDGET-001`; cassette replay works offline. The desktop still defaults to the template and has no bundled model vendor. Background runs can be cancelled before the next condition; a currently executing condition finishes first and sealed events remain intact. The [roadmap](../design/roadmap.md) identifies further recovery work.
