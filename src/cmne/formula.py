"""Bounded, closed formula language for narrative conditions.

All evaluation is total: unknown atoms yield None, and untrusted input can never
run Python code. The tri-state result is True, False, or None (undetermined).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import canonical, require

OPERATORS = {"atom", "not", "and", "or", "implies", "necessarily", "possibly",
             "believes", "suspends", "in_scenario"}
MAX_DEPTH = 16
MAX_NODES = 256


@dataclass(frozen=True)
class EvaluationContext:
    world: frozenset[str] = frozenset()
    false_world: frozenset[str] = frozenset()
    beliefs: dict[str, dict[str, str]] = field(default_factory=dict)
    scenarios: dict[str, frozenset[str]] = field(default_factory=dict)
    ranked_scenarios: tuple[str, ...] = ()


def atom_key(predicate: str | dict[str, Any]) -> str:
    if isinstance(predicate, str):
        return predicate
    require(isinstance(predicate, dict) and isinstance(predicate.get("name"), str)
            and isinstance(predicate.get("arguments", []), list),
            "E-FORMULA-001", "Atom needs a predicate name and argument list.")
    return canonical({"name": predicate["name"], "arguments": predicate.get("arguments", []),
                      "polarity": predicate.get("polarity", "positive")}).decode()


def validate(formula: dict[str, Any], max_depth: int = MAX_DEPTH,
             max_nodes: int = MAX_NODES) -> dict[str, Any]:
    count = 0

    def walk(node: Any, depth: int) -> None:
        nonlocal count
        count += 1
        require(count <= max_nodes and depth <= max_depth, "E-FORMULA-001",
                f"Formula exceeds {max_depth} levels or {max_nodes} nodes.")
        require(isinstance(node, dict) and node.get("op") in OPERATORS,
                "E-FORMULA-001", "Unknown or malformed formula operator.")
        op = node["op"]
        operands = node.get("operands", [])
        require(isinstance(operands, list), "E-FORMULA-001", "Operands must be a list.")
        if op == "atom":
            require(not operands and "predicate" in node, "E-FORMULA-001",
                    "Atom needs a predicate and no operands.")
            atom_key(node["predicate"])
            return
        needed = 2 if op == "implies" else 1 if op in (
            "not", "necessarily", "possibly", "believes", "suspends", "in_scenario") else None
        if needed is None:
            require(2 <= len(operands) <= 16, "E-FORMULA-001", "And/or needs 2–16 operands.")
        else:
            require(len(operands) == needed, "E-FORMULA-001", f"{op} needs {needed} operand(s).")
        if op in ("believes", "suspends"):
            require(isinstance(node.get("observer_id"), str) and node["observer_id"],
                    "E-FORMULA-001", f"{op} needs an observer ID.")
        if op == "in_scenario":
            require(isinstance(node.get("scenario_id"), str) and node["scenario_id"],
                    "E-FORMULA-001", "in_scenario needs a scenario ID.")
        for operand in operands:
            walk(operand, depth + 1)

    walk(formula, 1)
    return formula


def evaluate(formula: dict[str, Any], context: EvaluationContext) -> bool | None:
    validate(formula)

    def neg(value: bool | None) -> bool | None:
        return None if value is None else not value

    def conjunction(values: list[bool | None]) -> bool | None:
        return False if False in values else None if None in values else True

    def disjunction(values: list[bool | None]) -> bool | None:
        return True if True in values else None if None in values else False

    def walk(node: dict[str, Any], world: frozenset[str]) -> bool | None:
        op = node["op"]
        if op == "atom":
            key = atom_key(node["predicate"])
            if key in world:
                return True
            if key in context.false_world:
                return False
            return None
        operands = node["operands"]
        if op == "not":
            return neg(walk(operands[0], world))
        if op == "and":
            return conjunction([walk(item, world) for item in operands])
        if op == "or":
            return disjunction([walk(item, world) for item in operands])
        if op == "implies":
            return disjunction([neg(walk(operands[0], world)), walk(operands[1], world)])
        if op == "in_scenario":
            scenario = context.scenarios.get(node["scenario_id"])
            return walk(operands[0], scenario) if scenario is not None else None
        if op in ("necessarily", "possibly"):
            values = [walk(operands[0], context.scenarios[scenario])
                      for scenario in context.ranked_scenarios if scenario in context.scenarios]
            if not values:
                return None
            return conjunction(values) if op == "necessarily" else disjunction(values)
        # Belief and suspension are claims about an actor's explicit status, not world truth.
        target = operands[0]
        key = atom_key(target["predicate"]) if target["op"] == "atom" else canonical(target).decode()
        status = context.beliefs.get(node["observer_id"], {}).get(key)
        if status is None:
            return None
        return status == ("accepted" if op == "believes" else "suspended")

    return walk(formula, context.world)


def context_from_projection(projections: dict[str, Any]) -> EvaluationContext:
    actors = (projections["actor_a"], projections["actor_b"])
    return EvaluationContext(world=frozenset(atom_key(fact) for fact in projections["environment"]["facts"]),
                             beliefs={a["id"]: {claim: value["status"] for claim, value in a["beliefs"].items()}
                                      for a in actors})
