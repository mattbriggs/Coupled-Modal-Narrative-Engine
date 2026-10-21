"""Runtime shape contracts shared by the Python kernel and generated JSON Schema.

Semantic rules (access, causation, disclosure, etc.) live in ``core``. Shape
validation runs first so malformed input cannot become an uncaught TypeError.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, NotRequired, TypedDict


class Actor(TypedDict):
    id: str
    name: str


class Fixture(TypedDict):
    actors: list[Actor]
    entities: list[dict[str, Any]]
    initial_facts: NotRequired[list[str | dict[str, Any]]]
    style: NotRequired[dict[str, Any]]
    content_hash: NotRequired[str]


class NarrativeContract(TypedDict, total=False):
    required_story_conditions: list[str]
    forbidden_story_conditions: list[str]
    facts_that_must_be_clear: list[str]
    questions_that_must_remain_open: list[str]
    prose_bounds: dict[str, int]
    strain_threshold_bp: int
    strain_weights_bp: dict[str, int]
    high_commitment_bp: int
    repair_budget_bp: int
    voice: dict[str, Any]
    content_hash: str


class StoryPayload(TypedDict):
    title: str
    source_kind: NotRequired[str]
    kind: NotRequired[str]
    description: NotRequired[str]
    actor_ids: NotRequired[list[str]]
    entity_ids: NotRequired[list[str]]
    causal_parents: NotRequired[list[str]]
    observed_by: NotRequired[list[str]]
    world_facts: NotRequired[list[str | dict[str, Any]]]
    preconditions: NotRequired[list[dict[str, Any]]]
    strain_bp: NotRequired[int]
    strain_components_bp: NotRequired[dict[str, int]]
    crisis: NotRequired[dict[str, Any]]
    interpretations: NotRequired[list[dict[str, Any]]]
    modal_revision: NotRequired[dict[str, Any]]
    conceptual_revision: NotRequired[dict[str, Any]]


class DiscoursePayload(TypedDict):
    title: str
    source_kind: NotRequired[str]
    mode: NotRequired[str]
    story_refs: NotRequired[list[str]]
    text: NotRequired[str]
    focalizer: NotRequired[str]
    reveal: NotRequired[list[str]]
    cue: NotRequired[list[str]]
    withhold: NotRequired[list[str]]
    narrative_time: NotRequired[int]
    duration_weight_bp: NotRequired[int]
    salience_bp: NotRequired[int]


class Event(TypedDict):
    stream: str
    branch_id: str
    sequence: int
    schema_version: int
    payload: dict[str, Any]
    event_id: str
    integrity_hash: str
    stored_schema_version: NotRequired[int]
    effective_schema_version: NotRequired[int]


class TransitionResult(TypedDict):
    accepted: bool
    emitted_events: list[Event]
    rejected_reason: str | None
    invariant_results: list[dict[str, Any]]
    projection_hash_before: dict[str, str]
    projection_hash_after: dict[str, str]


class ErrorData(TypedDict):
    cmne_code: str
    field_path: str
    cause: str
    next_action: str


class RpcError(TypedDict):
    code: int
    message: str
    data: ErrorData


STRING = {"type": "string"}
INTEGER_BP = {"type": "integer", "minimum": 0, "maximum": 10000}
STRING_LIST = {"type": "array", "items": STRING}

SCHEMAS: dict[str, dict[str, Any]] = {
    "Actor": {"type": "object", "required": ["id", "name"], "properties": {
        "id": STRING, "name": STRING}},
    "Entity": {"type": "object", "required": ["id", "name"], "properties": {
        "id": STRING, "name": STRING, "kind": STRING, "motif": {"type": "boolean"}}},
    "Fixture": {"type": "object", "required": ["actors"], "properties": {
        "actors": {"type": "array", "minItems": 2, "maxItems": 2,
                   "items": {"$ref": "#/$defs/Actor"}},
        "entities": {"type": "array", "items": {"$ref": "#/$defs/Entity"}},
        "initial_facts": {"type": "array", "items": {"anyOf": [STRING, {"type": "object"}]}},
        "style": {"type": "object"},
        "content_hash": STRING}},
    "NarrativeContract": {"type": "object", "properties": {
        "required_story_conditions": STRING_LIST, "forbidden_story_conditions": STRING_LIST,
        "facts_that_must_be_clear": STRING_LIST, "questions_that_must_remain_open": STRING_LIST,
        "prose_bounds": {"type": "object", "required": ["min_words", "max_words"],
                         "properties": {"min_words": {"type": "integer", "minimum": 0},
                                        "max_words": {"type": "integer", "minimum": 0}}},
        "strain_threshold_bp": INTEGER_BP,
        "strain_weights_bp": {"type": "object", "properties": {
            name: INTEGER_BP for name in ("contradiction", "unexplained", "failed_prediction",
                                         "repair_complexity", "identity_goal")}},
        "high_commitment_bp": INTEGER_BP, "repair_budget_bp": INTEGER_BP,
        "voice": {"type": "object"}, "content_hash": STRING}},
    "StoryPayload": {"type": "object", "required": ["title"], "properties": {
        "title": STRING, "source_kind": {"type": "string", "enum": ["authored", "generated"]},
        "proposal_id": STRING, "validator_id": STRING,
        "kind": {"type": "string", "enum": ["action", "observation", "utterance",
            "recollection", "decision", "revision", "crisis"]}, "description": STRING,
        "actor_ids": STRING_LIST, "entity_ids": STRING_LIST, "causal_parents": STRING_LIST,
        "observed_by": STRING_LIST,
        "access_path": {"type": "string", "enum": ["perception", "testimony", "memory"]},
        "world_facts": {"type": "array", "items": {"anyOf": [STRING, {"type": "object"}]}},
        "interpretations": {"type": "array", "items": {"type": "object"}},
        "preconditions": {"type": "array", "items": {"type": "object"}},
        "strain_bp": INTEGER_BP, "belief_revision": {"type": "object"},
        "strain_components_bp": {"type": "object"}, "crisis": {"type": "object"},
        "remembered_story_sequences": {"type": "array", "items": {"type": "integer", "minimum": 1}},
        "modal_revision": {"type": "object"}, "conceptual_revision": {"type": "object"}}},
    "DiscoursePayload": {"type": "object", "required": ["title"], "properties": {
        "title": STRING, "source_kind": {"type": "string", "enum": ["authored"]},
        "mode": {"type": "string", "enum": ["scene", "summary", "ellipsis",
            "pause", "memory", "repetition"]}, "story_refs": STRING_LIST,
        "text": STRING, "focalizer": STRING, "reveal": STRING_LIST,
        "cue": STRING_LIST, "withhold": STRING_LIST,
        "narrative_time": {"type": "integer", "minimum": 0},
        "duration_weight_bp": INTEGER_BP, "salience_bp": INTEGER_BP,
        "variant": {"type": "string", "enum": ["authored", "suspense", "surprise", "dramatic_irony"]},
        "hypothetical": {"type": "boolean"}, "unreliable": {"type": "boolean"}}},
    "Event": {"type": "object", "required": ["stream", "branch_id", "sequence", "schema_version",
        "payload", "event_id", "integrity_hash"], "properties": {
        "stream": {"type": "string", "enum": ["story", "discourse", "evaluation"]},
        "branch_id": STRING, "sequence": {"type": "integer", "minimum": 1},
        "schema_version": {"type": "integer", "enum": [1, 2]}, "payload": {"type": "object"},
        "event_id": STRING, "integrity_hash": STRING,
        "stored_schema_version": {"type": "integer", "minimum": 1},
        "effective_schema_version": {"type": "integer", "minimum": 1}}},
    "Formula": {"type": "object", "required": ["op"], "properties": {
        "op": {"type": "string", "enum": ["atom", "not", "and", "or", "implies",
            "necessarily", "possibly", "believes", "suspends", "in_scenario"]},
        "operands": {"type": "array", "items": {"$ref": "#/$defs/Formula"}},
        "observer_id": STRING, "scenario_id": STRING,
        "predicate": {"anyOf": [STRING, {"type": "object"}]} }},
    "TransitionResult": {"type": "object", "required": ["accepted", "emitted_events",
        "rejected_reason", "invariant_results", "projection_hash_before", "projection_hash_after"],
        "properties": {"accepted": {"type": "boolean"},
                       "emitted_events": {"type": "array", "items": {"$ref": "#/$defs/Event"}},
                       "rejected_reason": {"anyOf": [STRING, {"type": "null"}]},
                       "invariant_results": {"type": "array", "items": {"type": "object"}},
                       "projection_hash_before": {"type": "object"},
                       "projection_hash_after": {"type": "object"}}},
    "ErrorData": {"type": "object", "required": ["cmne_code", "field_path", "cause", "next_action"],
        "properties": {"cmne_code": STRING, "field_path": STRING, "cause": STRING,
                       "next_action": STRING}},
    "RpcError": {"type": "object", "required": ["code", "message", "data"],
        "properties": {"code": {"type": "integer"}, "message": STRING,
                       "data": {"$ref": "#/$defs/ErrorData"}}},
    "ProjectionResult": {"type": "object", "required": ["projections", "hashes"],
        "properties": {"projections": {"type": "object"}, "hashes": {"type": "object"}}},
    "RunResult": {"type": "object", "required": ["run_id", "branch_id", "conditions", "prose",
        "findings", "stages", "packet_hash", "projection_hashes", "status"],
        "properties": {"run_id": STRING, "branch_id": STRING, "conditions": STRING_LIST,
                       "prose": STRING, "findings": {"type": "array", "items": {"type": "object"}},
                       "stages": {"type": "array", "items": {"type": "object"}},
                       "packet_hash": STRING, "projection_hashes": {"type": "object"},
                       "status": {"type": "string", "enum": ["passed", "failed"]}}}
}


def json_schema() -> dict[str, Any]:
    """Return the versioned JSON Schema document for exported RPC data."""
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/schema/cmne.schema.json",
            "$defs": deepcopy(SCHEMAS)}


def validate_shape(value: Any, name: str, path: str = "", code: str = "E-SCHEMA-001") -> None:
    """Validate the supported schema subset without executing untrusted input."""
    from .core import CmneError

    def walk(item: Any, schema: dict[str, Any], location: str) -> None:
        if "$ref" in schema:
            walk(item, SCHEMAS[schema["$ref"].rsplit("/", 1)[-1]], location)
            return
        if "anyOf" in schema:
            for option in schema["anyOf"]:
                try:
                    walk(item, option, location)
                    return
                except CmneError:
                    # An anyOf branch may reject the value; try the next branch.
                    pass
            raise CmneError(code, f"No allowed type matched at {location}.", location)
        kind = schema.get("type")
        if kind not in ("object", "array", "string", "integer", "boolean", "null"):
            raise CmneError(code, f"Unsupported schema type at {location or name}.", location)
        assert isinstance(kind, str)
        valid = {"object": lambda: isinstance(item, dict),
                 "array": lambda: isinstance(item, list),
                 "string": lambda: isinstance(item, str),
                 "integer": lambda: isinstance(item, int) and not isinstance(item, bool),
                 "boolean": lambda: isinstance(item, bool),
                 "null": lambda: item is None}[kind]()
        if not valid:
            raise CmneError(code, f"Expected {kind} at {location or name}.", location)
        if "enum" in schema and item not in schema["enum"]:
            raise CmneError(code, f"Invalid value at {location or name}.", location)
        if kind == "object":
            for required in schema.get("required", []):
                if required not in item:
                    raise CmneError(code, f"Missing {required}.",
                                    f"{location}.{required}".lstrip("."))
            for key, child in schema.get("properties", {}).items():
                if key in item:
                    walk(item[key], child, f"{location}.{key}".lstrip("."))
        elif kind == "array":
            if not schema.get("minItems", 0) <= len(item) <= schema.get("maxItems", 1_000_000):
                raise CmneError(code, f"Invalid array length at {location}.", location)
            if "items" in schema:
                for index, child_item in enumerate(item):
                    walk(child_item, schema["items"], f"{location}.{index}".lstrip("."))
        elif kind == "integer":
            if not schema.get("minimum", -2**63) <= item <= schema.get("maximum", 2**63-1):
                raise CmneError(code, f"Out-of-range integer at {location}.", location)

    walk(value, SCHEMAS[name], path)
