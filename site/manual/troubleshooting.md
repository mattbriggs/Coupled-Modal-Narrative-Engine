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
4. Seal after preview accepts it. Draft JSON persists in `<project>/drafts/` until sealed or deleted; after an interrupted session, reopen the project and inspect the recovered draft.

## Principle — preserve project integrity

Do not hand edit sealed NDJSON streams. The engine verifies event IDs, hashes, sequence, and schema when reading them. A second writer receives `E-LOCK-001`; close the first app/process before reopening the project. Back up the whole project directory when sharing or archiving a branch.

## Fact — current recovery scope

The shell can restart a failed sidecar once; saved drafts and sealed streams survive a normal process interruption. There is no model service or cost budget in the current release, so the model outage flow from scenario S-10 is a future feature. `run.cancel` reports that no asynchronous run is active; a run is synchronous. The [roadmap](../design/roadmap.md) identifies further recovery work.
