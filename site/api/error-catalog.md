# Error catalog

Each domain error has a stable code, cause, and corrective action. The JSON-RPC error data also carries `field_path` when a validator can locate the offending input.

| Code | Message | Cause | Next action |
|---|---|---|---|
| `E-ACCESS-001` | The observer cannot access this evidence. | An observer lacks a declared route to evidence. | Name the observer, access path, and accessible source event. |
| `E-ADAPTER-001` | The model adapter is unavailable or invalid. | A model adapter is unavailable or returned an invalid response. | Use the offline template or check the adapter manifest and response contract. |
| `E-APPEND-001` | The branch sequence is stale. | The branch head changed since the caller read it. | Reload the branch and submit against its current sequence. |
| `E-BELIEF-001` | The belief revision is invalid. | A belief revision is incomplete or out of range. | Supply an observer, claim, status, confidence, and accessible evidence. |
| `E-BRANCH-001` | The branch or fork point is invalid. | The branch or fork point is invalid. | Choose an existing branch and a sequence within its story history. |
| `E-BUDGET-001` | The model budget is exhausted. | A model run reached its call, token, or cost limit. | Inspect the recorded spend and set a new explicit budget before retrying. |
| `E-CASSETTE-001` | The model response cassette is missing or invalid. | A recorded model response is missing or fails integrity validation. | Record the canonical request first or restore its verified cassette. |
| `E-COMMAND-001` | The command batch is invalid. | The command has no supported event batch. | Submit nonempty story or discourse payloads. |
| `E-CONCEPT-001` | The conceptual revision is invalid. | A conceptual revision lacks a model transition. | Supply the observer, new concepts, and migration map. |
| `E-CONTRACT-001` | The narrative contract is invalid. | The narrative contract has a malformed or conflicting field. | Correct the reported contract field and validate again. |
| `E-CRISIS-001` | The model crisis is not eligible. | A crisis gate lacks strain, commitment, failed repair, or accessible evidence. | Supply accessible trigger evidence and a computed strain assessment above the threshold. |
| `E-DISCLOSURE-001` | The disclosure is not grounded. | A reveal is ungrounded or a withheld claim was already revealed. | Reference a grounding story event or correct the disclosure order. |
| `E-DISCOURSE-001` | The discourse act is invalid. | A discourse act has an invalid field or reference. | Correct the named act field and revalidate the draft. |
| `E-DRAFT-001` | The draft cannot be saved or sealed. | A draft is malformed or exceeds its limits. | Fix the draft node or edge and preview again. |
| `E-EXPORT-001` | There is no report to export. | There is no saved run for the selected branch. | Run the branch before exporting. |
| `E-FIXTURE-001` | The fixture is invalid. | The fixture cast or entity list is invalid. | Define exactly two distinct actors and unique named entities. |
| `E-FORMULA-001` | The formula is invalid or too large. | The formula is malformed or exceeds its bounds. | Use a supported operator and keep depth at most 16 and nodes at most 256. |
| `E-GRAPH-001` | The graph connection is invalid. | A graph connection is invalid or cyclic. | Reconnect compatible nodes without a causal cycle. |
| `E-INPUT-001` | The input file or path is unsafe or invalid. | Input is missing, unsafe, oversized, or malformed. | Use a valid JSON file inside the project and remove unsafe paths or tags. |
| `E-INTERPRET-001` | The interpretation is invalid. | An interpretation is missing provenance or targets the wrong event. | Name the observer, model version, claim, and earlier target sequences. |
| `E-LOCK-001` | The project writer lock prevents this change. | Another writer owns the project or a lock needs review. | Close the writer or explicitly clear a verified stale lock. |
| `E-MODAL-001` | The modal revision is invalid. | A modal revision has invalid observer or scenarios. | Supply a known observer and a scenario list. |
| `E-MODEL-001` | The modal model is inconsistent. | Active modal constraints conflict or a ranked scenario lacks a revision basis. | Remove the contradiction or cite a contradiction or revision event. |
| `E-PLAN-001` | The analysis plan is missing or invalid. | The analysis plan is absent or incomplete. | Save a complete plan before exporting a blinded evaluation set. |
| `E-PRECOND-001` | A command precondition does not hold. | A command precondition is not true before the event. | Inspect the preceding projection and revise the command or its evidence. |
| `E-PRIVACY-001` | Model data transfer has not been enabled. | Model data transfer was not enabled for this run. | Enable transfer explicitly after reviewing the fixture and evaluator data. |
| `E-PROJECT-001` | The project cannot be opened. | The project path is invalid or no project is open. | Open or create a valid project folder. |
| `E-PROSE-CAUSAL` | The prose contains an unsupported causal assertion. | A causal sentence lacks accessible story evidence. | Cite the story event that supports the cause or revise the sentence. |
| `E-PROSE-CLAIM` | The prose asserts a claim outside focal access. | An asserted claim is outside focal access. | Ground the claim in accessible evidence or mark it as hypothesis. |
| `E-PROSE-EARLY` | The prose reveals a claim too early. | A withheld claim appears before its planned reveal. | Move the claim to its reveal act or change the discourse plan. |
| `E-PROSE-ENTITY` | The prose introduces an unknown named entity. | A named entity does not occur in the fixture. | Add the entity to the fixture or remove the name. |
| `E-PROSE-FORBIDDEN` | The prose contains a forbidden assertion. | A forbidden literal assertion appears in prose. | Revise the authored text and run again. |
| `E-PROSE-PRIVATE` | The prose asserts private cognition outside focal access. | Prose asserts another actor's private cognition. | Recast it as a focalizer inference or provide licensed narration. |
| `E-PROSE-RESOLUTION` | The prose resolves an open question. | Prose explicitly settles a contractually open question. | Leave the question unresolved in this candidate. |
| `E-PROSE-WORDS` | The prose is outside its word bounds. | The passage is outside the contract's word bounds. | Revise discourse text or valid contract bounds and rerun. |
| `E-PROTO-001` | The sidecar protocol is incompatible. | The sidecar protocol version or request is incompatible. | Use a matching app and sidecar version, then reconnect. |
| `E-RESPONSE-001` | The evaluator response is invalid. | An evaluator response is malformed or duplicates an existing response. | Correct the named field and import the complete response batch again. |
| `E-RPC-001` | The RPC method is unavailable. | The requested RPC method is unknown or disallowed. | Use a documented method name. |
| `E-RPC-INPUT` | The RPC parameters are invalid. | RPC parameters are missing or malformed. | Supply the documented parameter names and value types. |
| `E-RUN-001` | The requested run cannot start. | The requested condition does not match the branch. | Select the branch for that condition or run the four sample branches in order. |
| `E-RUN-CONTRACT` | The story does not satisfy the contract. | A required story fact is absent. | Add the required fact to a valid story event and rerun. |
| `E-RUN-EMPTY` | The branch has no story events. | The branch has no story events. | Seal at least one story event. |
| `E-RUN-PLAN` | The branch has no telling plan. | The branch has no discourse acts. | Seal a discourse act tied to story. |
| `E-SAMPLE-001` | The bundled sample could not be created. | The bundled sample failed to initialize. | Recreate the sample with a matching package version. |
| `E-SCHEMA-001` | The schema version is unsupported. | The data schema or version is unsupported. | Use a supported schema or install a registered up-cast. |
| `E-STORE-001` | The stored data failed integrity verification. | Stored data failed integrity validation. | Restore a verified backup; do not edit sealed streams by hand. |
| `E-STORY-001` | The story event is invalid. | A story event has an invalid field or causal reference. | Correct the named event field and revalidate. |
| `E-STRAIN-001` | The strain assessment is invalid. | Strain weights or components are malformed. | Provide five integer components and weights totaling 10000 basis points. |
| `E-STUDY-001` | The study set is incomplete or invalid. | The study set is incomplete or an identifier is invalid. | Create three passing matched variants per condition and use a valid study ID. |
| `E-TRACE-001` | The trace target is invalid. | A trace target or observer is unknown. | Use a committed event, run, claim, and observer for the query. |
| `E-UPCAST-001` | The stored event cannot be up-cast. | No migration path exists for a stored event version. | Install a version with the required up-cast; preserve the stored bytes. |
| `E-VOICE-LENGTH` | A sentence violates the voice length rule. | A sentence exceeds the voice length rule. | Revise the sentence within the voice profile range. |
| `E-VOICE-PHRASE` | The prose contains a forbidden voice phrase. | A forbidden voice phrase appears. | Replace the phrase and check again. |

`E-RPC-INPUT` covers malformed RPC parameters; a programming fault is returned as a JSON-RPC internal error and should be reported with the request method and application version.
