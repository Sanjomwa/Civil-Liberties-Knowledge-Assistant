"""Session-wide safety fixtures for the unit test suite (docs/testing-design.md).

Hand-rolled network block chosen over adding `pytest-socket` as a new
dependency -- monkeypatching `socket.socket.connect` is a few lines and
this project already avoids dependencies it doesn't need (see
pyproject.toml's dependency list). Revisit only if this proves fragile.

Per the design doc's corrected mocking strategy: the real risk is a
network call happening at all, not merely OPENAI_API_KEY's presence (a
key can be passed to OpenAI(api_key=...) directly, bypassing an
env-based check). Blocking the actual socket connect is what makes "no
real API call, ever" true regardless of how a client got constructed.
"""

import socket

import pytest


class NetworkBlockedError(RuntimeError):
    """Raised when test code attempts a real network connection."""


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def _blocked_connect(self, *args, **kwargs):
        raise NetworkBlockedError(
            "Real network connection attempted during a test -- the unit "
            "test suite must never make a real network/API call. Mock the "
            "call instead."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    # Several modules (ground_truth.py, generate.py, judge.py, db.py) call
    # load_dotenv() at module-import time, before any fixture runs -- this
    # makes that harmless too, so a real key in .env is never picked up.
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
