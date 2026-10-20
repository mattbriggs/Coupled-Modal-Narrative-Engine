"""Canonical data, validation, replay, and deterministic scene construction.

The public functions take plain JSON-compatible values. The sidecar and CLI use
the same functions, keeping UI and transport out of narrative decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = 1
REDUCER_VERSION = 1
REALIZER_VERSION = 2
LENSES = ("fixture", "story", "discourse", "mind", "provenance", "motif", "pipeline")
STAGES = ("Validate", "Replay", "Revise", "Plan", "Packet", "Realize", "Check")


class CmneError(Exception):
    def __init__(self, code: str, message: str, field_path: str = "", next_action: str = ""):
        super().__init__(message)
        self.code = code
        self.field_path = field_path
        self.next_action = next_action

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
        raise CmneError(code, message, path, "Correct the indicated field and try again.")


def validate_fixture(fixture: dict) -> dict:
    require(isinstance(fixture, dict), "E-FIXTURE-001", "Fixture must be an object.")
    actors = fixture.get("actors", [])
    entities = fixture.get("entities", [])
    require(isinstance(actors, list) and len(actors) == 2,
            "E-FIXTURE-001", "A fixture needs exactly two actors.", "actors")
    require(all(isinstance(a, dict) and a.get("id") and a.get("name") for a in actors),
            "E-FIXTURE-001", "Each actor needs an id and name.", "actors")
    ids = [a["id"] for a in actors]
    require(len(set(ids)) == 2, "E-FIXTURE-001", "Actor IDs must differ.", "actors")
    require(isinstance(entities, list) and all(isinstance(e, dict) and e.get("id") and e.get("name") for e in entities),
            "E-FIXTURE-001", "Entities need an id and name.", "entities")
    require(len(set(ids + [e["id"] for e in entities])) == len(ids) + len(entities),
            "E-FIXTURE-001", "Entity IDs must be unique.", "entities")
    result = deepcopy(fixture)
    result.setdefault("version", 1)
    result["content_hash"] = digest({k: v for k, v in result.items() if k != "content_hash"})
    return result


def validate_contract(contract: dict) -> dict:
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
    c["content_hash"] = digest({k: v for k, v in c.items() if k != "content_hash"})
    return c


def validate_story_event(payload: dict, existing: list[dict], actor_ids: set[str]) -> dict:
    require(isinstance(payload, dict), "E-STORY-001", "Story event must be an object.")
    p = deepcopy(payload)
    require(isinstance(p.get("title"), str) and p["title"].strip(),
            "E-STORY-001", "Event title is required.", "title")
    require(p.get("kind", "action") in ("action", "observation", "utterance", "recollection", "decision", "revision", "crisis"),
            "E-STORY-001", "Unknown event kind.", "kind")
    p.setdefault("kind", "action")
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
    prior = {e["event_id"] for e in existing}
    require(all(parent in prior for parent in p["causal_parents"]),
            "E-STORY-001", "Causal parents must be earlier sealed events.", "causal_parents")
    require(isinstance(p["strain_bp"], int) and 0 <= p["strain_bp"] <= 10000,
            "E-STORY-001", "Strain must be 0–10000 basis points.", "strain_bp")
    require(isinstance(p["preconditions"], list), "E-FORMULA-001",
            "Preconditions must be a list of formulas.", "preconditions")
    from .formula import validate as validate_formula
    for formula in p["preconditions"]:
        validate_formula(formula)
    if p["kind"] == "observation":
        require(bool(p["observed_by"]) and p.get("access_path") in ("perception", "testimony", "memory"),
                "E-ACCESS-001", "Observation needs an observer and access path.", "access_path")
    for i, entry in enumerate(p["interpretations"]):
        require(entry.get("observer_id") in actor_ids and isinstance(entry.get("model_version"), int)
                and entry["model_version"] > 0 and entry.get("claim"),
                "E-INTERPRET-001", "Interpretation needs observer, model version, and claim.",
                f"interpretations.{i}")
        require(all(isinstance(seq, int) and 1 <= seq <= len(existing)
                    for seq in entry.get("target_story_sequences", [])),
                "E-INTERPRET-001", "An interpretation can target only earlier story events.",
                f"interpretations.{i}.target_story_sequences")
    if p.get("belief_revision"):
        revision = p["belief_revision"]
        require(revision.get("observer_id") in actor_ids and revision.get("claim")
                and revision.get("status") in ("accepted", "rejected", "suspended")
                and isinstance(revision.get("confidence_bp"), int)
                and 0 <= revision["confidence_bp"] <= 10000,
                "E-BELIEF-001", "Belief revision needs an observer, claim, status, and basis-point confidence.",
                "belief_revision")
        evidence_sequence = revision.get("evidence_story_sequence")
        require(isinstance(evidence_sequence, int) and 1 <= evidence_sequence <= len(existing)
                and revision["observer_id"] in existing[evidence_sequence - 1]["payload"].get("observed_by", []),
                "E-ACCESS-001", "Belief revision needs evidence the observer can access.",
                "belief_revision.evidence_story_sequence")
    if p.get("modal_revision"):
        revision = p["modal_revision"]
        require(revision.get("observer_id") in actor_ids and isinstance(revision.get("add_scenarios", []), list),
                "E-MODAL-001", "Modal revision needs an observer and scenarios.", "modal_revision")
    if p.get("conceptual_revision"):
        revision = p["conceptual_revision"]
        require(revision.get("observer_id") in actor_ids and isinstance(revision.get("concepts"), list)
                and isinstance(revision.get("migration_map"), dict),
                "E-CONCEPT-001", "Conceptual revision needs an observer, concepts, and migration map.",
                "conceptual_revision")
    return p


def validate_discourse_act(payload: dict, story: list[dict], previous: list[dict], actor_ids: set[str]) -> dict:
    require(isinstance(payload, dict), "E-DISCOURSE-001", "Act must be an object.")
    p = deepcopy(payload)
    require(isinstance(p.get("title"), str) and p["title"].strip(),
            "E-DISCOURSE-001", "Act title is required.", "title")
    require(p.get("mode", "scene") in ("scene", "summary", "ellipsis", "pause", "memory", "repetition"),
            "E-DISCOURSE-001", "Unknown discourse mode.", "mode")
    p.setdefault("mode", "scene")
    p.setdefault("story_refs", [])
    p.setdefault("reveal", [])
    p.setdefault("cue", [])
    p.setdefault("withhold", [])
    p.setdefault("text", "")
    p.setdefault("focalizer", "")
    require(not p["focalizer"] or p["focalizer"] in actor_ids,
            "E-DISCOURSE-001", "Unknown focalizer.", "focalizer")
    story_by_id = {e["event_id"]: e for e in story}
    require(all(ref in story_by_id for ref in p["story_refs"]),
            "E-DISCOURSE-001", "An act references an unknown story event.", "story_refs")
    available = set()
    for ref in p["story_refs"]:
        available.update(story_by_id[ref]["payload"].get("world_facts", []))
    require(all(claim in available for claim in p["reveal"]) or p.get("hypothetical") or p.get("unreliable"),
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
    seen = set()
    for index, event in enumerate(events, 1):
        body = {k: event[k] for k in ("stream", "branch_id", "sequence", "schema_version", "payload")}
        require(event["schema_version"] == SCHEMA_VERSION, "E-SCHEMA-001",
                f"Unknown schema version {event['schema_version']}.")
        require(event["stream"] == stream and event["branch_id"] in (allowed_branches or {branch_id})
                and event["sequence"] == index and event["event_id"] == stable_id("evt", body)
                and event["integrity_hash"] == digest(body) and event["event_id"] not in seen,
                "E-STORE-001", f"Corrupt {stream} event at sequence {index}.")
        seen.add(event["event_id"])


def replay(fixture: dict, contract: dict, story: list[dict], discourse: list[dict], sequence: int | None = None,
           discourse_index: int | None = None) -> dict:
    selected_story = story[:sequence] if sequence is not None else story
    selected_discourse = discourse[:discourse_index] if discourse_index is not None else discourse
    actors = {a["id"]: {"id": a["id"], "name": a["name"], "goals": a.get("goals", []),
                         "observations": [], "beliefs": {}, "interpretations": [],
                         "modal_model": deepcopy(a.get("modal_model", {"version": 1, "scenarios": []})),
                         "conceptual_model": deepcopy(a.get("conceptual_model", {"version": 1, "concepts": []}))}
              for a in fixture["actors"]}
    world = {"facts": list(fixture.get("initial_facts", [])), "events": []}
    tension = {"world_instability_bp": 0, "telling_tension_bp": 0, "series": []}
    reader = {"simulated": True, "revealed": [], "cued": [], "withheld": []}
    style = deepcopy(fixture.get("style", {"focalizer": fixture["actors"][0]["id"], "distance": "close"}))
    for event in selected_story:
        p = event["payload"]
        world["events"].append(event["event_id"])
        world["facts"].extend(f for f in p.get("world_facts", []) if f not in world["facts"])
        for actor_id in p.get("observed_by", []):
            actors[actor_id]["observations"].append(event["event_id"])
        if p.get("belief_revision"):
            revision = p["belief_revision"]
            actor = actors[revision["observer_id"]]
            actor["beliefs"][revision["claim"]] = {
                "status": revision["status"], "confidence_bp": revision["confidence_bp"],
                "evidence": [selected_story[revision["evidence_story_sequence"] - 1]["event_id"]]}
        if p.get("modal_revision"):
            revision = p["modal_revision"]
            actor = actors[revision["observer_id"]]
            model = actor["modal_model"]
            actor["modal_model"] = {**model, "version": model.get("version", 1) + 1,
                                    "scenarios": model.get("scenarios", []) + revision.get("add_scenarios", []),
                                    "allow_rivals": bool(revision.get("allow_rivals"))}
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
            record = {**interp, "source_event_id": event["event_id"],
                      "target_event_ids": [selected_story[seq - 1]["event_id"]
                                           for seq in interp.get("target_story_sequences", [])],
                      "id": stable_id("int", {"event": event["event_id"], "interpretation": interp})}
            actors[interp["observer_id"]]["interpretations"].append(record)
            actors[interp["observer_id"]]["beliefs"][interp["claim"]] = {
                "status": interp.get("status", "accepted"), "confidence_bp": interp.get("confidence_bp", 5000),
                "evidence": [event["event_id"]]}
        tension["world_instability_bp"] = p.get("strain_bp", tension["world_instability_bp"])
        tension["series"].append({"sequence": event["sequence"], "strain_bp": tension["world_instability_bp"]})
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
    for event in discourse:
        p = event["payload"]
        acts.append({"id": event["event_id"], "title": p["title"], "mode": p["mode"],
                     "text": p.get("text", ""), "reveal": p["reveal"], "withhold": p["withhold"],
                     "story": [by_id[ref]["payload"] for ref in p["story_refs"]]})
    packet = {"acts": acts, "fixture_id": fixture.get("id"), "realizer_version": REALIZER_VERSION,
              "sample_expansion": supports_expanded_sample(fixture, story) if fixture.get("id") == "mara-len" else False,
              "grounded_story_facts": projection["environment"]["facts"],
              "style": projection["prose_style"], "reader": projection["reader"],
              "forbidden_assertions": contract["forbidden_story_conditions"],
              "unresolved_questions": contract["questions_that_must_remain_open"],
              "word_bounds": contract["prose_bounds"]}
    return {**packet, "packet_hash": digest(packet)}


def template_realize(packet: dict) -> str:
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
    return "\n\n".join(chunks)


def check_realization(text: str, packet: dict) -> list[dict]:
    findings = []
    count = len(re.findall(r"\b[\w'-]+\b", text))
    bounds = packet["word_bounds"]
    if count < bounds["min_words"] or count > bounds["max_words"]:
        findings.append({"code": "E-PROSE-WORDS", "layer": "realization", "message":
                         f"{count} words falls outside {bounds['min_words']}–{bounds['max_words']}."})
    for assertion in packet["forbidden_assertions"]:
        if assertion and assertion.casefold() in text.casefold():
            findings.append({"code": "E-PROSE-FORBIDDEN", "layer": "grounding",
                             "message": f"Forbidden assertion appears: {assertion}"})
    return findings
