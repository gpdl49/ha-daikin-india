"""Shared fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from custom_components.daikin_india.dsiot import Transport

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest) -> None:
    """Load the integration from custom_components in Home Assistant tests."""
    if "hass" in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeTransport:
    """Records multireq traffic and answers reads from a fixture."""

    def __init__(self, status: dict[str, Any]) -> None:
        self.status = status
        self.writes: list[tuple[str, dict[str, Any]]] = []
        self.reads = 0

    async def read(self, targets: list[str]) -> list[dict[str, Any]]:
        self.reads += 1
        return copy.deepcopy(self.status["responses"][: len(targets)])

    async def write(self, to: str, pc: dict[str, Any]) -> dict[str, Any]:
        self.writes.append((to, pc))
        return {"fr": to, "rsc": 2004}


@pytest.fixture
def status() -> dict[str, Any]:
    return load_json("status_local.json")


@pytest.fixture
def fake_transport(status):
    """Patch the local transport's network calls with a fake."""
    fake = FakeTransport(status)

    async def _read(_self, targets):
        return await fake.read(targets)

    async def _write(_self, to, pc):
        return await fake.write(to, pc)

    with (
        patch.object(Transport, "read", _read),
        patch.object(Transport, "write", _write),
    ):
        yield fake
