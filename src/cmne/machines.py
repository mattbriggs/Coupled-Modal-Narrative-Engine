"""Pure, deterministic narrative-machine rules shared by commands and replay."""

from __future__ import annotations

from copy import deepcopy

from .core import digest, require, stable_id

STRAIN_DIMENSIONS = ("contradiction", "unexplained", "failed_prediction", "repair_complexity", "identity_goal")
REVISION_OPTIONS = ("preserve_or_deny", "local_repair", "modal_expansion",
                    "conceptual_revision", "hold_rival_models", "fragment", "suspend_judgment")
DEFAULT_WEIGHTS = {name: 2000 for name in STRAIN_DIMENSIONS}


def strain(contract: dict, payload: dict) -> dict:
    """Compute integer strain from five evidence assessments and contract weights.

    Older sealed events can carry only strain_bp; that historical value is kept
    for replay. New events with components use the derived score exclusively.
    """
    components = payload.get("strain_components_bp")
    if components is None:
        return {"score_bp": payload.get("strain_bp", 0), "components_bp": None,
                "weights_bp": None, "legacy": True}
    weights = contract.get("strain_weights_bp", DEFAULT_WEIGHTS)
    require(isinstance(components, dict) and set(components) == set(STRAIN_DIMENSIONS),
            "E-STRAIN-001", "Strain needs all five components.")
    require(isinstance(weights, dict) and set(weights) == set(STRAIN_DIMENSIONS)
            and all(type(v) is int and 0 <= v <= 10000 for v in weights.values())
            and sum(weights.values()) == 10000,
            "E-STRAIN-001", "Strain weights must be nonnegative basis points totaling 10000.")
    require(all(type(v) is int and 0 <= v <= 10000 for v in components.values()),
            "E-STRAIN-001", "Strain components must be integer basis points.")
    score = (sum(components[name] * weights[name] for name in STRAIN_DIMENSIONS) + 5000) // 10000
    return {"score_bp": score, "components_bp": deepcopy(components),
            "weights_bp": deepcopy(weights), "legacy": False}


def evidence_access(story: list[dict], observer: str, sequence: int) -> bool:
    return (type(sequence) is int and 1 <= sequence <= len(story)
            and observer in story[sequence - 1]["payload"].get("observed_by", []))


def crisis_assessment(contract: dict, story: list[dict], payload: dict) -> dict:
    crisis = payload.get("crisis", {})
    observer = crisis.get("observer_id")
    sequence = crisis.get("evidence_story_sequence")
    measure = strain(contract, payload)
    checks = {
        "material_strain": measure["score_bp"] >= contract.get("strain_threshold_bp", 6500),
        "high_commitment": type(crisis.get("commitment_bp")) is int
            and crisis["commitment_bp"] >= contract.get("high_commitment_bp", 7000),
        "repair_budget_exceeded": type(crisis.get("repair_cost_bp")) is int
            and crisis["repair_cost_bp"] > contract.get("repair_budget_bp", 5000),
        "evidence_accessible": evidence_access(story, observer, sequence),
    }
    return {"eligible": all(checks.values()), "checks": checks, "observer_id": observer,
            "evidence_story_sequence": sequence, "strain": measure,
            "options": list(REVISION_OPTIONS) if all(checks.values()) else []}


def validate_modal_model(model: dict) -> None:
    constraints = model.get("constraints", {})
    necessary = {digest(x) for x in constraints.get("necessary", [])}
    impossible = {digest(x) for x in constraints.get("impossible", [])}
    require(not necessary.intersection(impossible), "E-MODEL-001",
            "A proposition cannot be both necessary and impossible.")
    for scenario in model.get("ranked_scenarios", []):
        if not isinstance(scenario, dict) or not scenario.get("possible", False):
            continue
        violations = {digest(x) for x in scenario.get("violates_necessity", [])}
        require(not violations.intersection(necessary) or bool(scenario.get("contradiction_event_id")
                or scenario.get("revision_event_id")), "E-MODEL-001",
                "A possible scenario violating necessity needs a contradiction or revision event.")


def apply_modal_revision(model: dict, revision: dict, event_id: str) -> dict:
    result = deepcopy(model)
    result["version"] = model.get("version", 1) + 1
    result["supersedes"] = deepcopy(model)
    constraints = deepcopy(result.get("constraints", {}))
    for entry in revision.get("remove_necessity", []):
        constraints["necessary"] = [x for x in constraints.get("necessary", []) if x != entry]
    for name in ("necessary", "impossible", "contingent"):
        constraints.setdefault(name, [])
        constraints[name].extend(revision.get("add_" + name, []))
    result["constraints"] = constraints
    result["scenarios"] = model.get("scenarios", []) + revision.get("add_scenarios", [])
    result["ranked_scenarios"] = deepcopy(model.get("ranked_scenarios", []))
    for scenario in revision.get("ranked_scenarios", []):
        item = deepcopy(scenario)
        if item.get("violates_necessity") and not item.get("contradiction_event_id"):
            item["revision_event_id"] = event_id
        result["ranked_scenarios"].append(item)
    result["allow_rivals"] = bool(revision.get("allow_rivals", model.get("allow_rivals", False)))
    validate_modal_model(result)
    return result


def interpretation_record(interp: dict, event: dict, story: list[dict], prior: list[dict]) -> dict:
    target_ids = [story[n - 1]["event_id"] for n in interp.get("target_story_sequences", [])]
    superseded = [old["id"] for old in prior if set(old["target_event_ids"]) & set(target_ids)
                  and old["model_version"] < interp["model_version"]]
    evidence_ids = [story[n - 1]["event_id"] for n in interp.get("evidence_story_sequences", [])]
    if not evidence_ids:
        evidence_ids = [event["event_id"]]
    record = {**deepcopy(interp), "source_event_id": event["event_id"],
              "creating_event_id": event["event_id"], "target_event_ids": target_ids,
              "evidence_event_ids": evidence_ids, "producing_rules": interp.get("producing_rules", []),
              "model_id": interp.get("model_id", f"{interp['observer_id']}_conceptual"),
              "supersedes_interpretations": superseded}
    record["id"] = stable_id("int", {"event": event["event_id"], "interpretation": interp})
    record["provenance"] = {"holder": interp["observer_id"], "origin_type": "interpretation",
                            "source_event_ids": evidence_ids, "transformation_chain": [record["id"]],
                            "availability_story_sequence": event["sequence"],
                            "confidence_bp": interp.get("confidence_bp", 5000)}
    record["provenance"]["integrity_hash"] = digest(record["provenance"])
    return record


def epiphany_candidate(actor: dict, story: list[dict], contract: dict) -> dict:
    crises = actor.get("crises", [])
    latest = crises[-1] if crises else None
    interpretations = actor.get("interpretations", [])
    retrospective = [i for i in interpretations if i.get("supersedes_interpretations")]
    checks = {
        "operative_model_before_trigger": bool(latest and latest.get("model_version_before", 0) >= 1),
        "material_strain": bool(latest and latest["assessment"]["checks"]["material_strain"]),
        "registered_inadequacy": bool(latest and latest.get("registered_inadequacy")),
        "earlier_event_reinterpreted": bool(retrospective),
        "consequential_change": bool(latest and latest.get("consequence")),
        "projected_result": bool(latest and actor["conceptual_model"].get("version", 1) > 1),
        "no_abstract_lesson_required": not contract.get("require_abstract_lesson", False),
    }
    return {"label": "epiphany candidate", "candidate": all(checks.values()),
            "checks": checks, "retrospective_interpretation_ids": [i["id"] for i in retrospective]}
