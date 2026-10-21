"""In-memory event up-casts; sealed event bytes retain their original IDs."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from .core import CmneError, SCHEMA_VERSION

Upcast = Callable[[dict], dict]


def v1_to_v2(event: dict) -> dict:
    """Old story/discourse events predate adapters; evaluation claims keep their own origin."""
    payload = event["payload"]
    return ({**payload, "source_kind": "authored"}
            if event["stream"] in ("story", "discourse") else deepcopy(payload))


UPCASTERS: dict[int, Upcast] = {1: v1_to_v2}


def has_path(source_version: int, target_version: int = SCHEMA_VERSION,
             upcasters: dict[int, Upcast] | None = None) -> bool:
    handlers = UPCASTERS if upcasters is None else upcasters
    return (isinstance(source_version, int) and 1 <= source_version <= target_version
            and all(version in handlers for version in range(source_version, target_version)))


def upcast_event(event: dict, target_version: int = SCHEMA_VERSION,
                 upcasters: dict[int, Upcast] | None = None) -> dict:
    """Return a reducer view without changing the stored event envelope or hash."""
    handlers = UPCASTERS if upcasters is None else upcasters
    source = event["schema_version"]
    if not has_path(source, target_version, handlers):
        raise CmneError("E-UPCAST-001", f"No up-cast path from schema {source} to {target_version}.")
    if source == target_version:
        return event
    result = deepcopy(event)
    payload = deepcopy(event["payload"])
    for version in range(source, target_version):
        payload = handlers[version]({**event, "payload": payload})
        if not isinstance(payload, dict):
            raise CmneError("E-UPCAST-001", f"Up-cast from schema {version} returned no object.")
    result["payload"] = payload
    result["effective_schema_version"] = target_version
    result["stored_schema_version"] = source
    return result
