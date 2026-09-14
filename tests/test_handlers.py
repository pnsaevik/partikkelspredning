"""Tests for the platform-agnostic business logic.

These tests import `partikkelspredning.handlers` directly and never touch
`azure.functions` - the whole point of keeping the business logic
Azure-free is that it can be tested exactly like this, with no Functions
host and no Azure SDK involved.
"""
from partikkelspredning import handlers


def test_hello_returns_greeting_message():
    assert handlers.hello() == {"message": "Hello, world!"}
