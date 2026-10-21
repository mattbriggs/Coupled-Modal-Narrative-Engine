"""Offline, auditable evaluation-set and response contracts."""

from __future__ import annotations

import html
import math
import random
import re
from typing import Any
from itertools import combinations
from collections import Counter, defaultdict
from copy import deepcopy

from .core import digest, require, stable_id

PRIMARY_MEASURES = ("retrospective_citation", "distinct_details",
                    "preparedness", "unresolved_meaningful")
NULL_ALTERNATIVES = (
    "The conditions may not produce distinguishable reader experiences.",
    "The telling may conceal the state difference from readers.",
    "The measures or session may be too insensitive for this bounded scene.",
    "The conceptual revision may be structurally present without literary force.",
)


def validate_plan(plan: dict) -> dict:
    require(isinstance(plan, dict), "E-PLAN-001", "Analysis plan must be an object.")
    needed = ("hypotheses", "primary_measures", "secondary_measures", "target_sample_size",
              "sample_size_rationale", "agreement_metric", "exclusion_rules", "session_limit_minutes")
    for field in needed:
        require(field in plan, "E-PLAN-001", f"Analysis plan needs {field}.", field)
    require(isinstance(plan["hypotheses"], list) and bool(plan["hypotheses"])
            and all(isinstance(value, str) and value.strip() for value in plan["hypotheses"]),
            "E-PLAN-001", "State at least one testable hypothesis.", "hypotheses")
    require(isinstance(plan["primary_measures"], list)
            and all(isinstance(value, str) for value in plan["primary_measures"])
            and set(PRIMARY_MEASURES) <= set(plan["primary_measures"]),
            "E-PLAN-001", "Include the four primary measures.", "primary_measures")
    require(isinstance(plan["secondary_measures"], list)
            and all(isinstance(value, str) for value in plan["secondary_measures"]),
            "E-PLAN-001", "Secondary measures must be names.", "secondary_measures")
    require(bool(type(plan["target_sample_size"]) is int and plan["target_sample_size"] > 0
            and isinstance(plan["sample_size_rationale"], str) and plan["sample_size_rationale"].strip()),
            "E-PLAN-001", "Give a positive sample size and rationale.", "target_sample_size")
    require(plan["agreement_metric"] in ("percent_agreement", "cohen_kappa"),
            "E-PLAN-001", "Choose a supported agreement metric.", "agreement_metric")
    require(isinstance(plan["exclusion_rules"], list)
            and all(isinstance(value, str) for value in plan["exclusion_rules"]),
            "E-PLAN-001", "Exclusion rules must be text.", "exclusion_rules")
    require(type(plan["session_limit_minutes"]) is int and 1 <= plan["session_limit_minutes"] <= 180,
            "E-PLAN-001", "Session limit must be 1–180 minutes.", "session_limit_minutes")
    result = deepcopy(plan)
    result.pop("content_hash", None)
    result["content_hash"] = digest(result)
    return result


def protocol_html(plan: dict) -> str:
    limit = plan["session_limit_minutes"]
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>CMNE reading task</title>"
            "<main><h1>Reading task</h1><p>Read each passage and answer the questions below. "
            f"Allow up to {limit} minutes for the session. No answer is preferred. "
            "You may choose no discernible difference.</p><ol>"
            "<li>Which earlier detail, if any, changed meaning? Cite the exact span.</li>"
            "<li>How prepared or arbitrary did the change feel (1–5)?</li>"
            "<li>Was the unresolved ending meaningful, confusing, or neither?</li>"
            "<li>Rank the passages if a pair is shown, or choose no discernible difference.</li>"
            "</ol><p>Record a pseudonymous evaluator ID. Do not put your name in the response file.</p>"
            "</main></html>\n")


def passage_html(text: str, passage_id: str) -> str:
    paragraphs = "".join(f"<p>{html.escape(part)}</p>" for part in re.split(r"\n\s*\n", text) if part.strip())
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            f"<title>Passage {html.escape(passage_id)}</title><main><h1>Passage "
            f"{html.escape(passage_id)}</h1>{paragraphs}</main></html>\n")


def blinded_order(runs: list[dict], seed: int, plan_hash: str) -> tuple[list[dict], dict]:
    require(type(seed) is int, "E-STUDY-001", "Randomization seed must be an integer.")
    eligible = [run for run in runs if run.get("status") == "passed" and
                run.get("conditions", [None])[0] in ("C0", "C1", "C2", "C3")]
    counts = Counter(run["conditions"][0] for run in eligible)
    require(all(counts[condition] >= 3 for condition in ("C0", "C1", "C2", "C3")),
            "E-STUDY-001", "Save at least three passing realizations per condition before blind export.")
    chosen = [run for condition in ("C0", "C1", "C2", "C3")
              for run in sorted((item for item in eligible if item["conditions"][0] == condition),
                                key=lambda item: item["run_sequence"])[:3]]
    require(len({run["prose"] for run in chosen}) >= 12, "E-STUDY-001",
            "Matched realizations must be textually distinct; repeated copies are not independent candidates.")
    rng = random.Random(seed)
    rng.shuffle(chosen)
    entries = []
    key = {}
    for index, run in enumerate(chosen, 1):
        passage_id = stable_id("passage", [plan_hash, seed, index, run["run_id"]])
        entries.append({"passage_id": passage_id, "order": index, "text_hash": digest(run["prose"]),
                        "text_file": f"passages/{passage_id}.txt",
                        "html_file": f"passages/{passage_id}.html"})
        key[passage_id] = {"condition": run["conditions"][0], "branch_id": run["branch_id"],
                           "run_id": run["run_id"]}
    return entries, key


def validate_responses(rows: list[dict], key: dict, passages: dict[str, dict]) -> list[dict]:
    require(isinstance(rows, list), "E-RESPONSE-001", "Responses must be an array.")
    validated = []
    seen = set()
    for index, row in enumerate(rows):
        path = f"responses.{index}"
        require(isinstance(row, dict), "E-RESPONSE-001", "Response must be an object.", path)
        for field in ("evaluator_id", "passage_id", "text_version", "paired_ranking",
                      "free_response", "cited_spans", "confidence_bp", "no_discernible_difference",
                      "preparedness_rating", "resolution_class"):
            require(field in row, "E-RESPONSE-001", f"Missing {field}.", f"{path}.{field}")
        require(isinstance(row["evaluator_id"], str)
                and bool(re.fullmatch(r"[A-Za-z0-9_-]{3,48}", row["evaluator_id"])),
                "E-RESPONSE-001", "Use a pseudonymous evaluator ID of 3–48 safe characters.",
                f"{path}.evaluator_id")
        passage_id = row["passage_id"]
        require(isinstance(passage_id, str) and passage_id in key,
                "E-RESPONSE-001", "Unknown passage ID.", f"{path}.passage_id")
        require(row["text_version"] == passages[passage_id]["text_hash"],
                "E-RESPONSE-001", "Response text version differs from the exported passage.",
                f"{path}.text_version")
        unique = (row["evaluator_id"], passage_id)
        require(unique not in seen, "E-RESPONSE-001", "Duplicate evaluator/passage response.", path)
        seen.add(unique)
        require(row["paired_ranking"] in ("first", "second", "tie", "not_shown"),
                "E-RESPONSE-001", "Invalid paired ranking.", f"{path}.paired_ranking")
        require(isinstance(row["free_response"], str) and len(row["free_response"]) <= 10000,
                "E-RESPONSE-001", "Free response must be text under 10000 characters.",
                f"{path}.free_response")
        require(type(row["confidence_bp"]) is int and 0 <= row["confidence_bp"] <= 10000,
                "E-RESPONSE-001", "Confidence must be integer basis points.", f"{path}.confidence_bp")
        require(type(row["no_discernible_difference"]) is bool,
                "E-RESPONSE-001", "No-difference choice must be boolean.",
                f"{path}.no_discernible_difference")
        require(type(row["preparedness_rating"]) is int and 1 <= row["preparedness_rating"] <= 5,
                "E-RESPONSE-001", "Preparedness rating must be 1–5.",
                f"{path}.preparedness_rating")
        require(row["resolution_class"] in ("meaningful", "confusing", "neither"),
                "E-RESPONSE-001", "Resolution class is invalid.", f"{path}.resolution_class")
        text = passages[passage_id]["text"]
        require(isinstance(row["cited_spans"], list), "E-RESPONSE-001",
                "Cited spans must be an array.", f"{path}.cited_spans")
        for span_index, span in enumerate(row["cited_spans"]):
            require(isinstance(span, dict) and type(span.get("start")) is int
                    and type(span.get("end")) is int and 0 <= span["start"] < span["end"] <= len(text)
                    and isinstance(span.get("earlier_detail"), str), "E-RESPONSE-001",
                    "Span offsets must locate an earlier detail in the passage.",
                    f"{path}.cited_spans.{span_index}")
        validated.append({**deepcopy(row), "branch_id": key[passage_id]["branch_id"],
                          "condition": key[passage_id]["condition"]})
    return validated


def _wilson(successes: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.96
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [round(max(0.0, center-margin), 4), round(min(1.0, center+margin), 4)]


def analyze_responses(rows: list[dict], plan: dict, runs: list[dict]) -> dict:
    by_condition = defaultdict(list)
    for row in rows:
        by_condition[row["condition"]].append(row)
    measures: dict[str, dict[str, Any]] = {}
    for condition in ("C0", "C1", "C2", "C3"):
        group = by_condition[condition]
        n = len(group)
        citations = sum(bool(row["cited_spans"]) for row in group)
        meaningful = sum(row["resolution_class"] == "meaningful" for row in group)
        measures[condition] = {"responses": n,
            "retrospective_citation": {"proportion": citations/n if n else None,
                                        "confidence_interval_95": _wilson(citations, n)},
            "distinct_details": {"mean": sum(len({span["earlier_detail"] for span in row["cited_spans"]})
                                              for row in group)/n if n else None},
            "preparedness": {"mean": sum(row["preparedness_rating"] for row in group)/n if n else None},
            "unresolved_meaningful": {"proportion": meaningful/n if n else None,
                                      "confidence_interval_95": _wilson(meaningful, n)}}
    paired = defaultdict(list)
    for row in rows:
        paired[row["passage_id"]].append(row["resolution_class"])
    pairs = [pair for values in paired.values() for pair in combinations(values, 2)]
    agree = sum(left == right for left, right in pairs)
    agreement = {"metric": plan["agreement_metric"], "value": agree/len(pairs) if pairs else None,
                 "paired_items": len(pairs), "rated_passages": len(paired)}
    if plan["agreement_metric"] == "cohen_kappa" and any(len(values) > 2 for values in paired.values()):
        agreement["value"] = None
        agreement["not_computable_reason"] = "Cohen kappa requires exactly two ratings per paired passage."
    elif plan["agreement_metric"] == "cohen_kappa" and pairs:
        labels = ("meaningful", "confusing", "neither")
        first = Counter(values[0] for values in pairs)
        second = Counter(values[1] for values in pairs)
        chance = sum(first[label]*second[label] for label in labels)/(len(pairs)**2)
        agreement["value"] = (agree/len(pairs)-chance)/(1-chance) if chance < 1 else None
    effects: dict[str, dict[str, Any]] = {}
    for name in PRIMARY_MEASURES:
        left = measures["C0"][name]
        right = measures["C3"][name]
        key = "mean" if name in ("distinct_details", "preparedness") else "proportion"
        value = None if left[key] is None or right[key] is None else right[key]-left[key]
        # Binary intervals use conservative Wilson-bound differences. Continuous
        # contrasts use a fixed-seed percentile bootstrap over evaluator rows.
        interval = None
        if value is not None and "confidence_interval_95" in left:
            interval = [round(right["confidence_interval_95"][0]-left["confidence_interval_95"][1], 4),
                        round(right["confidence_interval_95"][1]-left["confidence_interval_95"][0], 4)]
        elif value is not None:
            def values(condition: str, measure_name: str = name) -> list[float]:
                group = by_condition[condition]
                if measure_name == "distinct_details":
                    return [float(len({span["earlier_detail"] for span in row["cited_spans"]})) for row in group]
                return [float(row["preparedness_rating"]) for row in group]
            c0, c3 = values("C0"), values("C3")
            rng = random.Random(173)
            draws = sorted(sum(rng.choice(c3) for _ in c3)/len(c3) -
                           sum(rng.choice(c0) for _ in c0)/len(c0) for _ in range(1000))
            interval = [round(draws[24], 4), round(draws[974], 4)]
        effects[name] = {"contrast": "C3 minus C0", "value": value, "confidence_interval_95": interval}
    candidate_counts = {condition: {"generated": sum(condition in run.get("conditions", []) for run in runs),
        "rejected": sum(condition in run.get("conditions", []) and run.get("status") != "passed" for run in runs)}
        for condition in ("C0", "C1", "C2", "C3")}
    contrary = [name for name, item in effects.items() if item["value"] is not None and item["value"] < 0]
    null = not rows or all(item["value"] is None or abs(item["value"]) < 0.05 for item in effects.values())
    return {"label": "descriptive human response analysis", "plan_hash": plan["content_hash"],
            "responses": len(rows), "primary_measures": measures, "agreement": agreement,
            "effect_sizes": effects, "candidate_counts": candidate_counts,
            "contrary_results": contrary, "null_result": null,
            "null_alternatives": list(NULL_ALTERNATIVES) if null else [],
            "limits": ["Small samples can produce unstable bootstrap intervals.",
                       "These descriptive results do not certify literary quality or causation."]}


def structural_measures(projections: dict, story: list[dict], discourse: list[dict],
                        ledger: dict, prose: str) -> dict:
    """Layer B measures are descriptive state observations, never aesthetic scores."""
    actor = projections["actor_a"]
    interpretations = actor["interpretations"]
    retrospective = [item for item in interpretations if item.get("supersedes_interpretations")]
    prior_targets = {target for item in interpretations if item["model_version"] == 1
                     for target in item["target_event_ids"]}
    story_positions = {event["event_id"]: event["sequence"] for event in story}
    depths = [story_positions[item["source_event_id"]] - story_positions[target]
              for item in retrospective for target in item["target_event_ids"]]
    words = re.findall(r"\b[\w'-]+\b", prose)
    explanations = len(re.findall(r"\b(?:because|therefore|meant that|in other words)\b",
                                  prose, flags=re.IGNORECASE))
    reader_reveals = set(projections["reader"]["revealed"])
    actor_claims = set(actor["beliefs"])
    motif = {entity_id: len(value["appearances"])
             for entity_id, value in ledger["entities"].items()}
    return {"label": "descriptive structural measures",
            "pre_crisis_model_coverage": {"interpreted_events": len(prior_targets),
                                          "story_events": min(7, len(story))},
            "contradiction_count": sum(belief["status"] == "rejected" for belief in actor["beliefs"].values()),
            "independent_contradiction_sources": len({source for record in actor["provenance"]
                                                        for source in record["source_event_ids"]}),
            "evidence_availability": {"actor_a_observed": len(actor["observations"]),
                                      "actor_b_observed": len(projections["actor_b"]["observations"])},
            "strain_trajectory_bp": [point["strain_bp"] for point in projections["tension"]["series"]],
            "reinterpretation_count": len(retrospective),
            "reinterpretation_depth": depths,
            "reader_character_alignment": {"shared_explicit_claims": len(reader_reveals & actor_claims),
                                           "reader_revealed": len(reader_reveals)},
            "resolution_state": "unresolved" if actor["conceptual_model"].get("unresolved_terms") else "undetermined",
            "explanatory_density_per_100_words": round(100*explanations/len(words), 3) if words else 0,
            "motif_recurrence": motif,
            "discourse_acts": len(discourse)}


ABLATIONS = ("remove_trigger", "remove_establishment_event", "reveal_secret_earlier",
             "replace_conceptual_with_fact", "state_insight_explicitly",
             "omit_retrospective_recurrence", "switch_reader_alignment")


def ablated_streams(name: str, story: list[dict], discourse: list[dict]) -> tuple[list[dict], list[dict]]:
    """Apply one controlled change to copies of sealed history for offline analysis."""
    require(name in ABLATIONS, "E-STUDY-001", "Unknown ablation.", "name")
    story_copy, discourse_copy = deepcopy(story), deepcopy(discourse)
    if name == "remove_trigger":
        story_copy = [event for event in story_copy if event["sequence"] != 7]
    elif name == "remove_establishment_event":
        story_copy = [event for event in story_copy if event["sequence"] != 1]
    elif name == "reveal_secret_earlier" and discourse_copy:
        discourse_copy[0]["payload"].setdefault("reveal", []).append("The note lists deferred departures")
    elif name == "replace_conceptual_with_fact":
        for event in story_copy:
            if event["payload"].get("conceptual_revision"):
                event["payload"].pop("conceptual_revision")
                event["payload"]["kind"] = "observation"
                event["payload"]["world_facts"] = ["Mara receives a new fact"]
    elif name == "state_insight_explicitly":
        for act in discourse_copy:
            if act["payload"].get("mode") == "pause":
                act["payload"]["text"] = "The repairs were care, not avoidance."
    elif name == "omit_retrospective_recurrence":
        discourse_copy = [act for act in discourse_copy if act["payload"].get("mode") != "memory"]
    elif name == "switch_reader_alignment" and discourse_copy:
        discourse_copy[0]["payload"]["focalizer"] = "len"
        discourse_copy[0]["payload"]["variant"] = "dramatic_irony"
    retained = {event["event_id"] for event in story_copy}
    for act in discourse_copy:
        act["payload"]["story_refs"] = [ref for ref in act["payload"].get("story_refs", []) if ref in retained]
    return story_copy, discourse_copy


def ablation_catalog(story: list[dict], discourse: list[dict]) -> list[dict]:
    """Return seven reproducible in-memory changes to compare against a base run."""
    result = []
    for name in ABLATIONS:
        story_copy, discourse_copy = ablated_streams(name, story, discourse)
        result.append({"name": name, "analysis_only": True,
                       "story_event_ids": [event["event_id"] for event in story_copy],
                       "discourse_act_ids": [act["event_id"] for act in discourse_copy],
                       "changed_payload_hash": digest({"story": [event["payload"] for event in story_copy],
                                                       "discourse": [act["payload"] for act in discourse_copy]})})
    return result


def ablation_prose(name: str, baseline: str, packet: dict) -> tuple[str, str]:
    """Make a controlled authored sample edit; otherwise use the altered packet."""
    paragraphs = baseline.split("\n\n")
    if not baseline.startswith("After Len left, the chair rocked once.") or len(paragraphs) < 7:
        from .core import template_realize
        return template_realize(packet), "altered_packet_template"
    if name == "remove_trigger":
        paragraphs = [p for p in paragraphs if not p.startswith("Under the bowl, a folded note waited.")]
        paragraphs = [p.replace("The dates on the note sent her back through the small acts she had already named: ",
                                "She returned to the small acts she had already named: ") for p in paragraphs]
    elif name == "remove_establishment_event":
        paragraphs = paragraphs[1:]
    elif name == "reveal_secret_earlier":
        paragraphs[0] = paragraphs[0].replace(
            "Mara watched it come to rest.",
            "Mara watched it come to rest. The note under the bowl listed dates on which Len meant to leave.", 1)
    elif name == "replace_conceptual_with_fact":
        paragraphs[5] = ("The dates on the note showed Len had planned to leave. Mara read each line twice. "
                         "She set the paper beside the bowl and kept it there while the light changed.")
    elif name == "state_insight_explicitly":
        paragraphs[5] = paragraphs[5].replace(
            "She could call it care. She could call it practice for leaving.",
            "The repairs were care, not avoidance. She finally understood Len's motive.", 1)
    elif name == "omit_retrospective_recurrence":
        paragraphs = [p for p in paragraphs if not p.startswith("She remembered the chair's loose joint")
                      and not p.startswith("Then the bowl:")]
    elif name == "switch_reader_alignment":
        paragraphs[0] = paragraphs[0].replace(
            "After Len left, the chair rocked once. Mara watched it come to rest.",
            "Before Len left, he watched the chair rock once. Mara stood beside the table.", 1)
    return "\n\n".join(paragraphs), "controlled_sample_edit"
