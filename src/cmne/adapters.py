"""Vendor-neutral model boundary with bounded calls and offline cassette replay.

Adapters receive plain JSON and return plain JSON. They never receive a Project,
event store, or command bus, so their output has no authority over canon.
"""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import json
import re
import subprocess
from typing import Any, Protocol, cast

from .core import CmneError, canonical, digest, require
from .project import contained, read_json, write_json


class ProposalAdapter(Protocol):
    def propose(self, request: dict[str, Any]) -> dict[str, Any]: ...


class ProseAdapter(Protocol):
    def realize(self, request: dict[str, Any]) -> dict[str, Any]: ...


OFFLINE_MANIFEST = {"model_name": "offline-template", "model_version": "2",
                    "prompt_version": "template-v2", "seed": 0,
                    "decoding": {"temperature_bp": 0, "max_output_tokens": 0}}


class CommandAdapter:
    """Invoke a researcher-supplied JSON-lines adapter without a shell.

The executable can obtain vendor credentials from its own environment. Its
    stderr is discarded because vendor diagnostics may contain secrets.
    """

    def __init__(self, argv: list[str], timeout_seconds: int = 60):
        require(bool(argv) and all(type(part) is str and bool(part) for part in argv)
                and type(timeout_seconds) is int and 1 <= timeout_seconds <= 600,
                "E-ADAPTER-001", "Adapter command or timeout is invalid.")
        self.argv = argv[:]
        self.timeout_seconds = timeout_seconds

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            completed = subprocess.run(self.argv, input=canonical(request) + b"\n",
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       timeout=self.timeout_seconds, check=False)
            if completed.returncode != 0 or len(completed.stdout) > 5 * 1024 * 1024:
                raise ValueError("adapter failed")
            response = json.loads(completed.stdout)
            if type(response) is not dict:
                raise ValueError("adapter returned a non-object")
            return response
        except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError) as exc:
            raise CmneError("E-ADAPTER-001", "Model adapter unavailable; use the offline template.") from exc

    def propose(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._invoke(request)

    def realize(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._invoke(request)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Accept only reproducibility fields; credential material stays with the vendor."""
    require(type(manifest) is dict, "E-ADAPTER-001", "Model manifest must be an object.")
    allowed = {"model_name", "model_version", "prompt_version", "seed", "decoding"}
    require(set(manifest) == allowed, "E-ADAPTER-001", "Model manifest has missing or unsafe fields.")
    for field in ("model_name", "model_version", "prompt_version"):
        require(type(manifest[field]) is str and bool(manifest[field].strip()),
                "E-ADAPTER-001", f"Model manifest needs {field}.")
    require(type(manifest["seed"]) is int and type(manifest["decoding"]) is dict,
            "E-ADAPTER-001", "Model seed and decoding settings are invalid.")
    require(set(manifest["decoding"]) <= {"temperature_bp", "top_p_bp", "max_output_tokens"},
            "E-ADAPTER-001", "Unknown decoding setting.")
    for name, value in manifest["decoding"].items():
        require(type(value) is int and 0 <= value <= (100000 if name == "max_output_tokens" else 10000),
                "E-ADAPTER-001", f"Invalid decoding setting: {name}.")
    canonical(manifest)
    return deepcopy(manifest)


class ModelGateway:
    """One run's shared budget and canonical request/response cassette.

    The caller must explicitly allow external data transfer in record mode.
    Replay reads only local cassette files, so it works with no adapter or socket.
    """

    def __init__(self, root: Path, manifest: dict[str, Any], mode: str,
                 budget: dict[str, Any], allow_data_transfer: bool = False):
        require(mode in ("record", "replay"), "E-ADAPTER-001", "Adapter mode must be record or replay.")
        self.root = root
        self.manifest = validate_manifest(manifest)
        self.mode = mode
        self.allow_data_transfer = allow_data_transfer
        require(type(budget) is dict and {"max_calls", "max_tokens"} <= set(budget)
                and set(budget) <= {"max_calls", "max_tokens", "max_cost_micros"},
                "E-BUDGET-001", "Budget needs maximum calls and tokens; cost is optional.")
        require(all(type(value) is int and value >= 0 for value in budget.values()),
                "E-BUDGET-001", "Budget limits must be nonnegative integers.")
        self.budget: dict[str, int | None] = {"max_cost_micros": None, **deepcopy(budget)}
        self.spend = {"calls": 0, "tokens": 0, "cost_micros": 0}

    def _check_budget(self) -> None:
        max_calls = cast(int, self.budget["max_calls"])
        max_tokens = cast(int, self.budget["max_tokens"])
        max_cost = self.budget["max_cost_micros"]
        if (self.spend["calls"] >= max_calls or self.spend["tokens"] >= max_tokens
                or (max_cost is not None and self.spend["cost_micros"] >= max_cost)):
            raise CmneError("E-BUDGET-001", f"Model budget reached; spend so far: {self.spend}.")

    def _charge(self, response: dict[str, Any]) -> None:
        usage = response.get("usage")
        require(type(usage) is dict and set(usage) == {"input_tokens", "output_tokens", "cost_micros"}
                and all(type(value) is int and value >= 0 for value in usage.values()),
                "E-ADAPTER-001", "Adapter must report nonnegative token and cost usage.")
        usage = cast(dict[str, int], usage)
        self.spend["calls"] += 1
        self.spend["tokens"] += usage["input_tokens"] + usage["output_tokens"]
        self.spend["cost_micros"] += usage["cost_micros"]

    @staticmethod
    def _reject_credentials(value: Any) -> None:
        """Reject credential-shaped fields and known environment secrets before persistence."""
        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if re.search(r"(?:api[_-]?key|auth(?:orization)?|credential|password|access[_-]?token|secret[_-]?key)",
                                 str(key), re.IGNORECASE):
                        raise CmneError("E-PRIVACY-001", "Credential field cannot enter model records.")
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)
        walk(value)
        encoded = canonical(value)
        for name, secret in os.environ.items():
            if (len(secret) >= 8 and re.search(r"(?:API_KEY|TOKEN|SECRET|PASSWORD)$", name.upper())
                    and secret.encode() in encoded):
                raise CmneError("E-PRIVACY-001", "Credential value cannot enter model records.")

    def call(self, role: str, payload: dict[str, Any], adapter: ProposalAdapter | ProseAdapter | None) -> dict[str, Any]:
        require(role in ("proposal", "prose") and type(payload) is dict,
                "E-ADAPTER-001", "Unknown model task or request payload.")
        self._check_budget()
        request = {"role": role, "manifest": self.manifest, "payload": deepcopy(payload)}
        self._reject_credentials(request)
        request_hash = digest(request)
        path = contained(self.root, "cassettes", f"{request_hash}.json")
        if self.mode == "replay":
            require(path.is_file(), "E-CASSETTE-001", "No recorded response for this request.")
            try:
                cassette = read_json(path)
            except CmneError as exc:
                raise CmneError("E-CASSETTE-001", "Recorded response is unreadable.") from exc
            require(cassette.get("request_hash") == request_hash and cassette.get("request") == request
                    and cassette.get("response_hash") == digest(cassette.get("response")),
                    "E-CASSETTE-001", "Recorded response failed integrity validation.")
            response = cassette["response"]
        else:
            require(self.allow_data_transfer, "E-PRIVACY-001",
                    "Enable data transfer for this run before calling a model adapter.")
            require(adapter is not None, "E-ADAPTER-001", "No model adapter is available.")
            try:
                response = (cast(ProposalAdapter, adapter).propose(deepcopy(request)) if role == "proposal"
                            else cast(ProseAdapter, adapter).realize(deepcopy(request)))
            except Exception as exc:
                # Vendor exceptions can contain request headers or credentials.
                raise CmneError("E-ADAPTER-001", "Model adapter unavailable; use the offline template.") from exc
            require(type(response) is dict and set(response) == {"output", "usage"}
                    and (type(response["output"]) is dict if role == "proposal" else type(response["output"]) is str),
                    "E-ADAPTER-001", "Adapter response has an invalid shape.")
        require(type(response) is dict and set(response) == {"output", "usage"}
                and (type(response["output"]) is dict if role == "proposal" else type(response["output"]) is str),
                "E-CASSETTE-001" if self.mode == "replay" else "E-ADAPTER-001",
                "Recorded response has an invalid shape.")
        self._reject_credentials(response)
        require(len(canonical(response)) <= 4 * 1024 * 1024, "E-ADAPTER-001",
                "Adapter response exceeds the cassette limit.")
        self._charge(response)
        if self.mode == "record":
            cassette = {"request_hash": request_hash, "request": request,
                        "response": response, "response_hash": digest(response)}
            if path.exists():
                require(read_json(path) == cassette, "E-CASSETTE-001",
                        "A different response is already recorded for this request.")
            else:
                write_json(path, cassette)
        return {"request_hash": request_hash, "output": deepcopy(response["output"]),
                "usage": deepcopy(response["usage"]), "spend": deepcopy(self.spend)}
