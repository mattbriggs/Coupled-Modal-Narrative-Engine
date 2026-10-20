# S-02 · Build a scene

## Goal

Create a bounded local project, record what happens, decide what the reader sees, and seal a runnable scene. This procedure uses the current GUI. For advanced fixture, contract, and revision fields, use the [JSON-RPC API](../api/json-rpc.md).

## Fact: current editing surface

The GUI can create a project and edit **story** and **discourse** drafts. New projects begin with two placeholder actors (`actor_a`, `actor_b`) and no entities. Fixture, Mind, and Motif are mostly inspection lenses today. The GUI does not yet provide a palette for adding actors, objects, rules, or full revision operators. Rename actors or add entities through `fixture.save` before writing events; see [contracts](../api/contracts.md).

## Procedure: create a project

1. Click the project name in the top bar and choose **Create new**.
2. Enter an absolute folder path that does not already contain a CMNE project, and a project name.
3. Click **Create project**. The new project opens in Story lens. If you keep the placeholder fixture, use `actor_a` and `actor_b` in actor fields.

**Result.** The folder has `project.cmne.json`, a fixture, a contract, and a `main` branch. The new default contract has no required story conditions and permits 0–1100 words.

## Structure: minimum authoring constructs

| Construct | What it stores | Authoring choice |
|---|---|---|
| Fixture | Two actors, entities, initial facts, style | Choose the cast and objects before sealing events |
| Contract | Required/forbidden story claims, open questions, word bounds, strain threshold | Decide what the passage must and must not assert |
| Story event | Title, kind, participants, observations, optional facts/revisions, strain | Say what happened in story time |
| Discourse act | Mode, text, focalizer, story references, reveal/withhold | Decide when and how the reader encounters an event |
| Draft | Editable nodes and edges | Work before committing to canon |
| Sealed event | Validated event in the NDJSON stream | Preserve the branch's history |

## Procedure: add story events

1. Open **Story** and choose **Add event**. Select the draft node.
2. In the inspector, enter a specific **Title** and **Description**. Choose an event kind: action, observation, utterance, recollection, decision, revision, or crisis.
3. Enter actor IDs in **Actors**. For an observation, enter at least one **Observed by** ID and choose a **perception**, **testimony**, or **memory** access path. The sidecar rejects an observation without these fields.
4. Set the strain slider if the event increases or eases pressure. The stored value is an integer from 0 to 10,000 basis points; the UI displays a percentage.
5. To record causation, select a draft event, click **Connect from**, then select the target story event. The sidecar checks the connection; a sealed event cannot gain a new causal parent.
6. Repeat for each beat. Click **Seal draft**. Correct any field or connection errors reported by the preview, then seal again.

**Result.** The event or group of draft events is appended to the branch's story stream. Sealed events cannot be edited in place; [fork to revise](revise-compare.md).

## Procedure: plan discourse

1. Open **Discourse** and choose **Add act**. Select the new draft act.
2. Choose a mode such as **scene**, **summary**, **memory**, or **pause**. Enter **Passage text** and select a focalizer or narrator.
3. Select the act and click **Connect from**, then select the story event it discloses. This creates a `refs` edge from the act to the event.
4. If you use **Reveal claims**, each claim must match a `world_facts` value on a referenced story event. The GUI does not expose `world_facts` editing yet, so leave Reveal empty when using the GUI alone. A claim already revealed cannot later be withheld.
5. Seal the discourse draft. Add more acts in the order the reader should encounter them, which may differ from story order.

**Result.** A run can produce prose from the acts' text. For custom projects, the offline realizer joins the authored act text in discourse order; it does not invent missing scenes. Set enough text to satisfy your contract's word bounds.

## Principle: keep private knowledge out of observed events

An observation must name who had access and how. This is a narrow validation rule in the current release. The prose checker does not yet reliably detect every sentence that implies another character's private thought. Write and review the passage accordingly.

## Next step

[Generate and export](generate-export.md) the passage, then [read its findings](read-output.md).
