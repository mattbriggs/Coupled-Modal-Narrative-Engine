"""Canonical data, validation, replay, and deterministic scene construction.

The public functions take plain JSON-compatible values. The sidecar and CLI use
the same functions, keeping UI and transport out of narrative decisions.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = 2
REDUCER_VERSION = 2
REALIZER_VERSION = 2
LENSES = ("fixture", "story", "discourse", "mind", "provenance", "motif", "pipeline")
STAGES = ("Validate", "Replay", "Revise", "Plan", "Packet", "Realize", "Check")


class CmneError(Exception):
    def __init__(self, code: str, message: str, field_path: str = "", next_action: str = ""):
        super().__init__(message)
        self.code = code
        self.field_path = field_path
        from .errors import guidance
        self.next_action = next_action or guidance(code)[1]

    def as_dict(self) -> dict:
        return {"cmne_code": self.code, "field_path": self.field_path,
                "next_action": self.next_action, "cause": str(self)}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{digest(value)[:16]}"


def require(condition: bool, code: str, message: str, path: str = "") -> None:
    if not condition:
        raise CmneError(code, message, path)


def validate_fixture(fixture: dict) -> dict:
    from .contracts import validate_shape
    validate_shape(fixture, "Fixture", code="E-FIXTURE-001")
    require(isinstance(fixture, dict), "E-FIXTURE-001", "Fixture must be an object.")
    actors = fixture.get("actors", [])
    entities = fixture.get("entities", [])
    require(isinstance(actors, list) and len(actors) == 2,
            "E-FIXTURE-001", "A fixture needs exactly two actors.", "actors")
    require(all(isinstance(a, dict) and a.get("id") and a.get("name") for a in actors),
            "E-FIXTURE-001", "Each actor needs an id and name.", "actors")
    ids = [a["id"] for a in actors]
    require(len(set(ids)) == 2, "E-FIXTURE-001", "Actor IDs must differ.", "actors")
    from .machines import validate_modal_model
    for actor in actors:
        validate_modal_model(actor.get("modal_model", {}))
    require(isinstance(entities, list) and all(isinstance(e, dict) and e.get("id") and e.get("name") for e in entities),
            "E-FIXTURE-001", "Entities need an id and name.", "entities")
    require(len(set(ids + [e["id"] for e in entities])) == len(ids) + len(entities),
            "E-FIXTURE-001", "Entity IDs must be unique.", "entities")
    result = deepcopy(fixture)
    result.setdefault("version", 1)
    result.setdefault("entities", [])
    result["content_hash"] = digest({k: v for k, v in result.items() if k != "content_hash"})
    return result


def validate_contract(contract: dict) -> dict:
    from .contracts import validate_shape
    validate_shape(contract, "NarrativeContract", code="E-CONTRACT-001")
    require(isinstance(contract, dict), "E-CONTRACT-001", "Contract must be an object.")
    c = deepcopy(contract)
    c.setdefault("version", 1)
    c.setdefault("required_story_conditions", [])
    c.setdefault("forbidden_story_conditions", [])
    c.setdefault("facts_that_must_be_clear", [])
    c.setdefault("questions_that_must_remain_open", [])
    c.setdefault("prose_bounds", {"min_words": 0, "max_words": 1100})
    c.setdefault("strain_threshold_bp", 6500)
    for field in ("required_story_conditions", "forbidden_story_conditions",
                  "facts_that_must_be_clear", "questions_that_must_remain_open"):
        require(isinstance(c[field], list), "E-CONTRACT-001", f"{field} must be a list.", field)
    require(not set(c["required_story_conditions"]) & set(c["forbidden_story_conditions"]),
            "E-CONTRACT-001", "Required and forbidden conditions overlap.", "required_story_conditions")
    require(not set(c["facts_that_must_be_clear"]) & set(c["questions_that_must_remain_open"]),
            "E-CONTRACT-001", "A claim cannot be both clear and open.", "facts_that_must_be_clear")
    bounds = c["prose_bounds"]
    require(isinstance(bounds, dict) and isinstance(bounds.get("min_words"), int)
            and isinstance(bounds.get("max_words"), int)
            and 0 <= bounds["min_words"] <= bounds["max_words"],
            "E-CONTRACT-001", "Word bounds must be ordered nonnegative integers.", "prose_bounds")
    require(isinstance(c["strain_threshold_bp"], int) and 0 <= c["strain_threshold_bp"] <= 10000,
            "E-CONTRACT-001", "Strain threshold must be 0–10000 basis points.", "strain_threshold_bp")
    from .machines import DEFAULT_WEIGHTS, STRAIN_DIMENSIONS
    weights = c.get("strain_weights_bp", DEFAULT_WEIGHTS)
    require(isinstance(weights, dict) and set(weights) == set(STRAIN_DIMENSIONS)
            and all(type(v) is int and 0 <= v <= 10000 for v in weights.values())
            and sum(weights.values()) == 10000,
            "E-CONTRACT-001", "Strain weights must total 10000 basis points.", "strain_weights_bp")
    for field in ("high_commitment_bp", "repair_budget_bp"):
        if field in c:
            require(type(c[field]) is int and 0 <= c[field] <= 10000,
                    "E-CONTRACT-001", f"{field} must be integer basis points.", field)
    c["content_hash"] = digest({k: v for k, v in c.items() if k != "content_hash"})
    return c


def validate_story_event(payload: dict, existing: list[dict], actor_ids: set[str],
                         entity_ids: set[str] | None = None, contract: dict | None = None,
                         initial_models: dict | None = None) -> dict:
    from .contracts import validate_shape
    validate_shape(payload, "StoryPayload", code="E-STORY-001")
    require(isinstance(payload, dict), "E-STORY-001", "Story event must be an object.")
    p = deepcopy(payload)
    require(isinstance(p.get("title"), str) and p["title"].strip(),
            "E-STORY-001", "Event title is required.", "title")
    require(p.get("kind", "action") in ("action", "observation", "utterance", "recollection", "decision", "revision", "crisis"),
            "E-STORY-001", "Unknown event kind.", "kind")
    p.setdefault("kind", "action")
    p.setdefault("source_kind", "authored")
    require(p["source_kind"] in ("authored", "generated"), "E-STORY-001", "Unknown event source kind.")
    if p["source_kind"] == "generated":
        require(isinstance(p.get("proposal_id"), str) and p["proposal_id"]
                and p.get("validator_id") == "cmne-command-validator-v2", "E-STORY-001",
                "Generated events need a proposal ID and accepting validator.")
    p.setdefault("description", "")
    p.setdefault("actor_ids", [])
    p.setdefault("entity_ids", [])
    p.setdefault("causal_parents", [])
    p.setdefault("observed_by", [])
    p.setdefault("world_facts", [])
    p.setdefault("interpretations", [])
    p.setdefault("preconditions", [])
    p.setdefault("strain_bp", 0)
    require(all(a in actor_ids for a in p["actor_ids"] + p["observed_by"]),
            "E-STORY-001", "Unknown actor.", "actor_ids")
    if entity_ids is not None:
        require(all(entity in entity_ids for entity in p["entity_ids"]),
                "E-STORY-001", "Unknown entity.", "entity_ids")
    prior = {e["event_id"] for e in existing}
    require(all(parent in prior for parent in p["causal_parents"]),
            "E-STORY-001", "Causal parents must be earlier sealed events.", "causal_parents")
    require(isinstance(p["strain_bp"], int) and 0 <= p["strain_bp"] <= 10000,
            "E-STORY-001", "Strain must be 0–10000 basis points.", "strain_bp")
    from .machines import apply_modal_revision, crisis_assessment, evidence_access, strain
    strain(contract or {}, p)
    require(isinstance(p["preconditions"], list), "E-FORMULA-001",
            "Preconditions must be a list of formulas.", "preconditions")
    from .formula import validate as validate_formula
    for formula in p["preconditions"]:
        validate_formula(formula)
    if p["kind"] == "observation":
        require(bool(p["observed_by"]) and p.get("access_path") in ("perception", "testimony", "memory"),
                "E-ACCESS-001", "Observation needs an observer and access path.", "access_path")
    for i, entry in enumerate(p["interpretations"]):
        require(entry.get("observer_id") in actor_ids and type(entry.get("model_version")) is int
                and entry["model_version"] > 0 and isinstance(entry.get("claim"), str)
                and bool(entry["claim"]),
                "E-INTERPRET-001", "Interpretation needs observer, model version, and claim.",
                f"interpretations.{i}")
        require(all(type(seq) is int and 1 <= seq <= len(existing)
                    for seq in entry.get("target_story_sequences", [])),
                "E-INTERPRET-001", "An interpretation can target only earlier story events.",
                f"interpretations.{i}.target_story_sequences")
        evidence = entry.get("evidence_story_sequences", [])
        require(all(evidence_access(existing, entry["observer_id"], seq) for seq in evidence)
                and (bool(evidence) or entry["observer_id"] in p["observed_by"]
                     or p["kind"] == "crisis"),
                "E-ACCESS-001", "Interpretation needs accessible evidence.",
                f"interpretations.{i}.evidence_story_sequences")
    if p.get("belief_revision"):
        revision = p["belief_revision"]
        require(revision.get("observer_id") in actor_ids and isinstance(revision.get("claim"), str)
                and bool(revision["claim"])
                and revision.get("status") in ("accepted", "rejected", "suspended")
                and type(revision.get("confidence_bp")) is int
                and 0 <= revision["confidence_bp"] <= 10000,
                "E-BELIEF-001", "Belief revision needs an observer, claim, status, and basis-point confidence.",
                "belief_revision")
        evidence_sequence = revision.get("evidence_story_sequence")
        require(type(evidence_sequence) is int and 1 <= evidence_sequence <= len(existing)
                and revision["observer_id"] in existing[evidence_sequence - 1]["payload"].get("observed_by", []),
                "E-ACCESS-001", "Belief revision needs evidence the observer can access.",
                "belief_revision.evidence_story_sequence")
    if p.get("modal_revision"):
        revision = p["modal_revision"]
        require(revision.get("observer_id") in actor_ids and isinstance(revision.get("add_scenarios", []), list),
                "E-MODAL-001", "Modal revision needs an observer and scenarios.", "modal_revision")
        sequence = revision.get("evidence_story_sequence")
        require(sequence is None or evidence_access(existing, revision["observer_id"], sequence),
                "E-ACCESS-001", "Modal revision evidence must be accessible.",
                "modal_revision.evidence_story_sequence")
        model = (initial_models or {}).get(revision["observer_id"], {"version": 1})
        for event in existing:
            previous = event["payload"].get("modal_revision")
            if previous and previous.get("observer_id") == revision["observer_id"]:
                model = apply_modal_revision(model, previous, event["event_id"])
        apply_modal_revision(model, revision, "proposed_revision")
    if p.get("conceptual_revision"):
        revision = p["conceptual_revision"]
        require(revision.get("observer_id") in actor_ids and isinstance(revision.get("concepts"), list)
                and isinstance(revision.get("migration_map"), dict),
                "E-CONCEPT-001", "Conceptual revision needs an observer, concepts, and migration map.",
                "conceptual_revision")
    if p["kind"] == "crisis":
        require(contract is not None, "E-CRISIS-001", "A crisis requires an active contract.")
        assert contract is not None
        assessment = crisis_assessment(contract, existing, p)
        require(assessment["eligible"], "E-CRISIS-001",
                "Crisis requires accessible evidence, material strain, high commitment, and a failed repair budget.")
        require(p.get("conceptual_revision") or p.get("modal_revision") or p.get("belief_revision")
                or p.get("crisis", {}).get("revision_option"), "E-CRISIS-001",
                "A crisis must record a revision option or transition.")
    return p


def validate_discourse_act(payload: dict, story: list[dict], previous: list[dict], actor_ids: set[str]) -> dict:
    from .contracts import validate_shape
    validate_shape(payload, "DiscoursePayload", code="E-DISCOURSE-001")
    require(isinstance(payload, dict), "E-DISCOURSE-001", "Act must be an object.")
    p = deepcopy(payload)
    require(isinstance(p.get("title"), str) and p["title"].strip(),
            "E-DISCOURSE-001", "Act title is required.", "title")
    require(p.get("mode", "scene") in ("scene", "summary", "ellipsis", "pause", "memory", "repetition"),
            "E-DISCOURSE-001", "Unknown discourse mode.", "mode")
    p.setdefault("mode", "scene")
    p.setdefault("source_kind", "authored")
    p.setdefault("story_refs", [])
    p.setdefault("reveal", [])
    p.setdefault("cue", [])
    p.setdefault("withhold", [])
    p.setdefault("text", "")
    p.setdefault("focalizer", "")
    p.setdefault("narrative_time", max((e["sequence"] for e in story if e["event_id"] in p["story_refs"]), default=0))
    p.setdefault("duration_weight_bp", 5000)
    p.setdefault("salience_bp", 5000)
    p.setdefault("variant", "authored")
    require(type(p["narrative_time"]) is int and 0 <= p["narrative_time"] <= len(story),
            "E-DISCOURSE-001", "Narrative time must name a committed story point.", "narrative_time")
    for field in ("duration_weight_bp", "salience_bp"):
        require(type(p[field]) is int and 0 <= p[field] <= 10000,
                "E-DISCOURSE-001", f"{field} must be integer basis points.", field)
    require(p["variant"] in ("authored", "suspense", "surprise", "dramatic_irony"),
            "E-DISCOURSE-001", "Unknown telling variant.", "variant")
    require(not p["focalizer"] or p["focalizer"] in actor_ids,
            "E-DISCOURSE-001", "Unknown focalizer.", "focalizer")
    story_by_id = {e["event_id"]: e for e in story}
    require(all(ref in story_by_id for ref in p["story_refs"]),
            "E-DISCOURSE-001", "An act references an unknown story event.", "story_refs")
    available = []
    for ref in p["story_refs"]:
        available.extend(story_by_id[ref]["payload"].get("world_facts", []))
    require(bool(all(claim in available for claim in p["reveal"]) or p.get("hypothetical") or p.get("unreliable")),
            "E-DISCLOSURE-001", "Revealed claims must be grounded in referenced story events.", "reveal")
    already = {claim for act in previous for claim in act["payload"].get("reveal", [])}
    require(not already.intersection(p["withhold"]), "E-DISCLOSURE-001",
            "A claim already revealed cannot be withheld.", "withhold")
    return p


def make_event(stream: str, branch_id: str, sequence: int, payload: dict) -> dict:
    body = {"stream": stream, "branch_id": branch_id, "sequence": sequence,
            "schema_version": SCHEMA_VERSION, "payload": payload}
    return {**body, "event_id": stable_id("evt", body), "integrity_hash": digest(body)}


def verify_events(events: list[dict], stream: str, branch_id: str,
                  allowed_branches: set[str] | None = None) -> None:
    from .contracts import validate_shape
    from .upcast import has_path, upcast_event
    seen = set()
    for index, event in enumerate(events, 1):
        try:
            validate_shape(event, "Event", code="E-STORE-001")
        except CmneError as exc:
            raise CmneError("E-STORE-001", f"Corrupt {stream} event at line {index}: {exc}") from exc
        body = {k: event[k] for k in ("stream", "branch_id", "sequence", "schema_version", "payload")}
        require(set(event) == set(body) | {"event_id", "integrity_hash"}, "E-STORE-001",
                f"Unexpected field in {stream} event at line {index}.")
        require(has_path(event["schema_version"], SCHEMA_VERSION), "E-UPCAST-001",
                f"No up-cast path for schema version {event['schema_version']}.")
        require(event["stream"] == stream and event["branch_id"] in (allowed_branches or {branch_id})
                and event["sequence"] == index and event["event_id"] == stable_id("evt", body)
                and event["integrity_hash"] == digest(body) and event["event_id"] not in seen,
                "E-STORE-001", f"Corrupt {stream} event at line {index}.")
        if stream in ("story", "discourse"):
            effective = upcast_event(event)
            validate_shape(effective["payload"], "StoryPayload" if stream == "story" else "DiscoursePayload",
                           code="E-STORE-001")
            require(effective["payload"].get("source_kind") in ("authored", "generated"), "E-STORE-001",
                    f"Missing or invalid event source at line {index}.")
        seen.add(event["event_id"])


def replay(fixture: dict, contract: dict, story: list[dict], discourse: list[dict], sequence: int | None = None,
           discourse_index: int | None = None) -> dict:
    from .machines import (apply_modal_revision, crisis_assessment, epiphany_candidate,
                           interpretation_record, strain, validate_modal_model)
    selected_story = story[:sequence] if sequence is not None else story
    selected_discourse = discourse[:discourse_index] if discourse_index is not None else discourse
    actors: dict[str, dict[str, Any]] = {a["id"]: {"id": a["id"], "name": a["name"], "goals": a.get("goals", []),
                         "physical_state": {}, "observations": [], "beliefs": {},
                         "belief_history": [], "interpretations": [], "provenance": [], "crises": [],
                         "event_horizon": 0,
                         "modal_model": deepcopy(a.get("modal_model", {"version": 1, "scenarios": []})),
                         "conceptual_model": deepcopy(a.get("conceptual_model", {"version": 1, "concepts": []}))}
              for a in fixture["actors"]}
    for actor in actors.values():
        validate_modal_model(actor["modal_model"])
    world: dict[str, Any] = {"facts": list(fixture.get("initial_facts", [])), "events": []}
    tension: dict[str, Any] = {"world_instability_bp": 0, "telling_tension_bp": 0, "series": []}
    reader: dict[str, Any] = {"simulated": True, "revealed": [], "cued": [], "withheld": []}
    style = deepcopy(fixture.get("style", {"focalizer": fixture["actors"][0]["id"], "distance": "close"}))
    for event in selected_story:
        p = event["payload"]
        world["events"].append(event["event_id"])
        world["facts"].extend(f for f in p.get("world_facts", []) if f not in world["facts"])
        for actor_id in p.get("observed_by", []):
            actors[actor_id]["observations"].append(event["event_id"])
            actors[actor_id]["event_horizon"] = event["sequence"]
            for entity_id in p.get("entity_ids", []):
                actors[actor_id]["physical_state"][entity_id] = event["event_id"]
        if p.get("belief_revision"):
            revision = p["belief_revision"]
            actor = actors[revision["observer_id"]]
            belief = {
                "status": revision["status"], "confidence_bp": revision["confidence_bp"],
                "evidence": [selected_story[revision["evidence_story_sequence"] - 1]["event_id"]]}
            actor["beliefs"][revision["claim"]] = belief
            actor["belief_history"].append({"claim": revision["claim"], **belief,
                                            "creating_event_id": event["event_id"]})
            provenance = {"holder": revision["observer_id"], "claim": revision["claim"],
                          "origin_type": "belief_revision", "source_event_ids": belief["evidence"],
                          "transformation_chain": [event["event_id"]],
                          "availability_story_sequence": event["sequence"],
                          "confidence_bp": revision["confidence_bp"]}
            actor["provenance"].append({**provenance, "integrity_hash": digest(provenance)})
        if p.get("modal_revision"):
            revision = p["modal_revision"]
            actor = actors[revision["observer_id"]]
            actor["modal_model"] = apply_modal_revision(actor["modal_model"], revision, event["event_id"])
        if p.get("conceptual_revision"):
            revision = p["conceptual_revision"]
            actor_id = revision.get("observer_id")
            if actor_id in actors:
                old = actors[actor_id]["conceptual_model"]
                actors[actor_id]["conceptual_model"] = {"version": old.get("version", 1) + 1,
                    "supersedes": old, "concepts": revision.get("concepts", []),
                    "migration_map": revision.get("migration_map", {}),
                    "unresolved_terms": revision.get("unresolved_terms", [])}
        for interp in p.get("interpretations", []):
            actor = actors[interp["observer_id"]]
            record = interpretation_record(interp, event, selected_story, actor["interpretations"])
            actor["interpretations"].append(record)
            actor["provenance"].append({**record["provenance"], "claim": interp["claim"],
                                        "interpretation_id": record["id"]})
            belief = {
                "status": interp.get("status", "accepted"), "confidence_bp": interp.get("confidence_bp", 5000),
                "evidence": record["evidence_event_ids"]}
            actor["beliefs"][interp["claim"]] = belief
            actor["belief_history"].append({"claim": interp["claim"], **belief,
                                            "creating_event_id": event["event_id"]})
        if p.get("kind") == "crisis":
            assessment = crisis_assessment(contract, selected_story[:event["sequence"] - 1], p)
            observer = p.get("crisis", {}).get("observer_id")
            if observer in actors:
                actors[observer]["crises"].append({"event_id": event["event_id"],
                    "assessment": assessment,
                    "model_version_before": actors[observer]["conceptual_model"].get("version", 1) -
                        int(bool(p.get("conceptual_revision"))),
                    "registered_inadequacy": bool(p["crisis"].get("registered_inadequacy")),
                    "consequence": p["crisis"].get("consequence")})
        measure = strain(contract, p)
        tension["world_instability_bp"] = measure["score_bp"]
        tension["series"].append({"sequence": event["sequence"], "strain_bp": measure["score_bp"],
                                  "components_bp": measure["components_bp"]})
    selected_ids = set(world["events"])
    for act in selected_discourse:
        if not set(act["payload"].get("story_refs", [])).issubset(selected_ids):
            continue
        p = act["payload"]
        reader["revealed"].extend(p.get("reveal", []))
        reader["cued"].extend(p.get("cue", []))
        reader["withheld"].extend(p.get("withhold", []))
        if p.get("focalizer"):
            style["focalizer"] = p["focalizer"]
    tension["telling_tension_bp"] = min(10000, len(reader["withheld"]) * 1200)
    for actor in actors.values():
        actor["epiphany_candidate"] = epiphany_candidate(actor, selected_story, contract)
    projections = {"actor_a": actors[fixture["actors"][0]["id"]],
                   "actor_b": actors[fixture["actors"][1]["id"]],
                   "environment": world, "tension": tension, "reader": reader, "prose_style": style}
    return {"projections": projections, "hashes": {k: digest({"fixture": fixture["content_hash"],
            "contract": contract["content_hash"], "reducer": REDUCER_VERSION, "state": v})
            for k, v in projections.items()}}


def build_packet(fixture: dict, contract: dict, story: list[dict], discourse: list[dict]) -> dict:
    from .sample import supports_expanded_sample
    projection = replay(fixture, contract, story, discourse)["projections"]
    by_id = {e["event_id"]: e for e in story}
    acts = []
    reader_state: dict[str, Any] = {"simulated": True, "revealed": [], "cued": [], "withheld": []}
    licensed_claims = list(fixture.get("narrator_facts", []))
    named = [a["name"] for a in fixture["actors"]] + [e["name"] for e in fixture.get("entities", [])]
    remembered: dict[str, set[int]] = {actor["id"]: set() for actor in fixture["actors"]}
    for event in story:
        p = event["payload"]
        for observer in p.get("observed_by", []):
            remembered[observer].update(p.get("remembered_story_sequences", []))
    for event in discourse:
        p = event["payload"]
        focalizer = p.get("focalizer") or projection["prose_style"].get("focalizer")
        accessible = [source for source in story if focalizer in source["payload"].get("observed_by", [])
                      or focalizer in source["payload"].get("actor_ids", [])
                      or source["sequence"] in remembered.get(focalizer, set())]
        accessible_ids = {source["event_id"] for source in accessible}
        focal_facts = [fact for source in accessible for fact in source["payload"].get("world_facts", [])]
        for fact in focal_facts:
            if fact not in licensed_claims:
                licensed_claims.append(fact)
        before = deepcopy(reader_state)
        for field, source in (("revealed", "reveal"), ("cued", "cue"), ("withheld", "withhold")):
            for item in p.get(source, []):
                if item not in reader_state[field]:
                    reader_state[field].append(item)
        acts.append({"id": event["event_id"], "title": p["title"], "mode": p["mode"],
                     "discourse_index": event["sequence"],
                     "narrative_time": p.get("narrative_time", max(
                         (by_id[ref]["sequence"] for ref in p["story_refs"]), default=0)),
                     "duration_weight_bp": p.get("duration_weight_bp", 5000),
                     "salience_bp": p.get("salience_bp", 5000),
                     "variant": p.get("variant", "authored"),
                     "focalizer": focalizer, "focal_access_event_ids": sorted(accessible_ids),
                     "reader_before": before, "reader_after": deepcopy(reader_state),
                     "text": p.get("text", ""), "reveal": p["reveal"], "cue": p["cue"],
                     "withhold": p["withhold"], "story_refs": p["story_refs"],
                     "story": [by_id[ref]["payload"] if ref in accessible_ids else {
                         "title": by_id[ref]["payload"]["title"], "description": "",
                         "world_facts": []} for ref in p["story_refs"]]})
    disclosure_schedule = {}
    for index, act in enumerate(acts):
        for claim in act["withhold"]:
            disclosure_schedule[claim] = next((later for later in range(index + 1, len(acts))
                                               if claim in acts[later]["reveal"]), None)
    resolution_patterns = []
    if any("care" in question.casefold() and "avoidance" in question.casefold()
           for question in contract["questions_that_must_remain_open"]):
        resolution_patterns.append(r"\b(?:len's acts|the repairs|the repair|the chair repair|the bowl replacement|it)\s+(?:was|were|meant|proved)\s+(?:only\s+)?(?:care|avoidance)\b")
    packet = {"acts": acts, "fixture_id": fixture.get("id"), "realizer_version": REALIZER_VERSION,
              "sample_expansion": supports_expanded_sample(fixture, story) if fixture.get("id") == "mara-len" else False,
              "grounded_story_facts": projection["environment"]["facts"],
              "style": projection["prose_style"], "reader": projection["reader"],
              "known_names": named, "actor_names": {a["id"]: a["name"] for a in fixture["actors"]},
              "licensed_claims": licensed_claims, "disclosure_schedule": disclosure_schedule,
              "resolution_patterns": resolution_patterns,
              "voice": contract.get("voice", fixture.get("voice", {})),
              "forbidden_assertions": contract["forbidden_story_conditions"],
              "unresolved_questions": contract["questions_that_must_remain_open"],
              "word_bounds": contract["prose_bounds"]}
    return {**packet, "packet_hash": digest(packet)}


def template_realize(packet: dict, variant_index: int = 0) -> str:
    chunks = []
    for act in packet["acts"]:
        if packet.get("sample_expansion"):
            from .sample import expanded_sample_text
            expanded = expanded_sample_text(act["title"], act["text"])
            if expanded:
                chunks.append(expanded)
                continue
        if act["text"].strip():
            chunks.append(act["text"].strip())
        elif act["story"]:
            chunks.append(" ".join((e.get("description") or e["title"]).strip() for e in act["story"]))
    prose = "\n\n".join(chunks)
    if variant_index == 1:
        prose = prose.replace("Mara watched", "She watched", 1)
    elif variant_index == 2:
        prose = prose.replace("the bowl", "the blue bowl", 1)
    return prose


def check_realization(text: str, packet: dict) -> list[dict]:
    from .prose import check_candidate
    return check_candidate(text, packet)[1]
