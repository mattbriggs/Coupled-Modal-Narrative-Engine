"""Deterministic prose boundary: read-only realization and grounded checking."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Protocol


class ProseRealizer(Protocol):
    def realize(self, packet: dict) -> str: ...


class TemplateRealizer:
    def realize(self, packet: dict) -> str:
        from .core import template_realize
        return template_realize(deepcopy(packet))


def _sentences(text: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text.strip()) if piece.strip()]


def annotate_candidate(text: str, packet: dict, annotations: list[dict] | None = None) -> list[dict]:
    """Map sentences to their discourse act and classify explicit claim markers.

    A model or editor can supply sentence annotations. The deterministic path
    conservatively infers assertions, hypotheses, metaphors, and free thought.
    """
    result: list[dict] = []
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    for paragraph_index, paragraph in enumerate(paragraphs):
        act = packet.get("acts", [])[min(paragraph_index, len(packet.get("acts", [])) - 1)] if packet.get("acts") else {}
        for sentence in _sentences(paragraph):
            lowered = sentence.casefold()
            if re.search(r"\b(could|might|may|perhaps|possibly|if)\b", lowered):
                claim_type = "hypothesis"
            elif re.search(r"\b(like|as if)\b", lowered) or re.search(
                    r"\b(?:bowl|chair|note|room) was (?:a|an) (?:small|bright|dark|silent|pale)?\s*"
                    r"(?:moon|sea|wound|mirror|island|ghost)\b", lowered):
                claim_type = "metaphor"
            elif re.search(r"\b(?:she|he) (?:thought|wondered|remembered)\b", lowered):
                claim_type = "free_indirect_thought"
            else:
                claim_type = "assertion"
            index = len(result)
            supplied = annotations[index] if annotations and index < len(annotations) else {}
            supplied_type = supplied.get("claim_type", claim_type)
            # An adapter's annotation may add claims but cannot turn an
            # unhedged assertion into a harmless metaphor or hypothesis.
            if claim_type == "assertion" and supplied_type in (
                    "metaphor", "hypothesis", "free_indirect_thought"):
                supplied_type = "assertion"
            result.append({"index": index, "text": sentence, "discourse_act_id": act.get("id"),
                           "focalizer": act.get("focalizer", packet.get("style", {}).get("focalizer")),
                           "claim_type": supplied_type,
                           "claims": supplied.get("claims", []),
                           "grounding_source_ids": supplied.get("grounding_source_ids",
                                                              [source for source in act.get("story_refs", [])
                                                               if source in act.get("focal_access_event_ids", [])]),
                           "access": supplied.get("access", "unknown")})
    return result


def check_candidate(text: str, packet: dict, annotations: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Return sentence records and deterministic hard findings with layer ownership."""
    sentences = annotate_candidate(text, packet, annotations)
    findings: list[dict] = []
    def fail(code: str, layer: str, message: str, index: int | None = None) -> None:
        finding: dict[str, str | int] = {"code": code, "layer": layer, "message": message}
        if index is not None:
            finding["sentence_index"] = index
        findings.append(finding)

    count = len(re.findall(r"\b[\w'-]+\b", text))
    bounds = packet["word_bounds"]
    if count < bounds["min_words"] or count > bounds["max_words"]:
        fail("E-PROSE-WORDS", "realization", f"{count} words falls outside {bounds['min_words']}–{bounds['max_words']}.")
    for assertion in packet.get("forbidden_assertions", []):
        if assertion and assertion.casefold() in text.casefold():
            fail("E-PROSE-FORBIDDEN", "grounding", f"Forbidden assertion appears: {assertion}")

    allowed_names = {name.casefold() for name in packet.get("known_names", [])}
    actor_names = packet.get("actor_names", {})
    acts_by_id = {act["id"]: act for act in packet.get("acts", [])}
    known_claims = {claim for act in packet.get("acts", [])
                    for claim in act.get("licensed_claims", []) if isinstance(claim, str)}
    forbidden_resolutions = packet.get("resolution_patterns", [])
    voice = packet.get("voice", {})
    max_words = voice.get("sentence_max_words")
    min_words = voice.get("sentence_min_words")
    for sentence in sentences:
        index, lowered = sentence["index"], sentence["text"].casefold()
        act = acts_by_id.get(sentence["discourse_act_id"], {})
        licensed_claims = act.get("licensed_claims", packet.get("licensed_claims", []))
        source_ids = set(act.get("focal_access_event_ids", []))
        claim_type = sentence["claim_type"]
        word_count = len(re.findall(r"\b[\w'-]+\b", sentence["text"]))
        if max_words is not None and word_count > max_words:
            fail("E-VOICE-LENGTH", "realization", "Sentence exceeds voice word limit.", index)
        if min_words is not None and word_count < min_words:
            fail("E-VOICE-LENGTH", "realization", "Sentence falls below voice word limit.", index)
        for phrase in voice.get("forbidden_phrases", []):
            if phrase.casefold() in lowered:
                fail("E-VOICE-PHRASE", "realization", f"Voice forbids: {phrase}", index)
        for pattern in forbidden_resolutions:
            if re.search(pattern, lowered) and claim_type == "assertion":
                fail("E-PROSE-RESOLUTION", "grounding", "An open question is explicitly resolved.", index)
                break
        focalizer = sentence["focalizer"]
        if packet.get("style", {}).get("distance") == "close" and focalizer:
            for actor_id, actor_name in actor_names.items():
                if actor_id == focalizer:
                    continue
                name = re.escape(actor_name.casefold())
                private = (rf"\b{name}\s+(?:(?:had|has|would)\s+)?(?:(?:secretly|privately)\s+)?"
                           rf"(?:known|knew|thought|felt|wanted|intended|meant|planned|hoped|believed|"
                           rf"suspected|feared)\b")
                hedged_private = re.search(rf"\b(?:perhaps|maybe|might|could|may|if)\s+{name}\b", lowered)
                match = re.search(private, lowered)
                if match and not hedged_private:
                    lead = lowered[max(0, match.start() - 60):match.start()]
                    reported_inference = re.search(
                        r"(?:no longer|not|never)\s+(?:proved|showed|established|implied)(?:\s+that)?\s*$"
                        r"|(?:wondered|imagined|suspected)\s+(?:whether|if|that)\s*$", lead)
                    if not reported_inference:
                        fail("E-PROSE-PRIVATE", "grounding",
                             "Another actor's private cognition is outside focal access.", index)
                        break
        if claim_type in ("metaphor", "hypothesis", "free_indirect_thought"):
            continue
        for claim in known_claims:
            if claim not in licensed_claims and re.search(rf"\b{re.escape(claim.casefold())}\b", lowered):
                fail("E-PROSE-CLAIM", "grounding", f"Claim lacks focal access: {claim}", index)
        for claim in sentence["claims"]:
            if claim not in licensed_claims:
                fail("E-PROSE-CLAIM", "grounding", f"Claim lacks focal access: {claim}", index)
        if (re.search(r"\b(because|therefore|caused|made him|made her)\b", lowered)
                and (not sentence["grounding_source_ids"]
                     or not set(sentence["grounding_source_ids"]).issubset(source_ids))):
            fail("E-PROSE-CAUSAL", "story", "Causal assertion needs story evidence.", index)
        # Proper names are checked against the fixture catalog. Common sentence
        # openers are excluded; a writer can provide explicit claims for ambiguity.
        for name in re.findall(r"\b[A-Z][a-z]{2,}\b", sentence["text"]):
            if sentence["text"].startswith(name):
                continue
            if name.casefold() not in allowed_names and name not in {"After", "Before", "Then", "The", "She", "He", "It", "Under", "At", "A", "An", "But", "And", "Neither", "Care", "Avoidance", "One", "Each", "What", "That", "Her", "His", "There", "When", "Still", "Someone", "Perhaps"}:
                fail("E-PROSE-ENTITY", "grounding", f"Unknown named entity: {name}", index)
        for claim, reveal_index in packet.get("disclosure_schedule", {}).items():
            if claim.casefold() in lowered and sentence["discourse_act_id"]:
                act_index = next((i for i, act in enumerate(packet["acts"])
                                  if act["id"] == sentence["discourse_act_id"]), 0)
                if reveal_index is None or act_index < reveal_index:
                    fail("E-PROSE-EARLY", "discourse", f"Claim appears before planned reveal: {claim}", index)
    return sentences, findings
