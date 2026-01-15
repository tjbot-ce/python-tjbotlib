import pytest
from tjbot.error import TJBotError

def test_tjbot_error_basic():
    err = TJBotError("Something went wrong")
    assert str(err) == "Something went wrong"
    assert err.code is None

def test_tjbot_error_with_code():
    err = TJBotError("Missing hardware", code="HARDWARE_NOT_FOUND")
    assert err.code == "HARDWARE_NOT_FOUND"

def test_tjbot_error_with_context():
    context = {"hw": "led", "pin": 12}
    err = TJBotError("GPIO error", context=context)
    assert err.context == context

def test_tjbot_error_with_cause():
    original = ValueError("Bad value")
    err = TJBotError("Wrapper error", cause=original)
    assert err.cause == original
