# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from tjbot.utils.errors import TJBotError


def test_creates_error_with_message_only():
    error = TJBotError("Test error message")
    assert isinstance(error, Exception)
    assert isinstance(error, TJBotError)
    assert str(error) == "Test error message"


def test_creates_error_with_code_option():
    error = TJBotError("Test error", code="INVALID_CONFIG")
    assert error.code == "INVALID_CONFIG"
    assert str(error) == "Test error"


def test_creates_error_with_context_option():
    context = {"userId": 123, "action": "initialize"}
    error = TJBotError("Test error", context=context)
    assert error.context == context


def test_creates_error_with_cause_option():
    original_error = ValueError("Original error")
    error = TJBotError("Wrapped error", cause=original_error)
    assert error.cause is original_error
    assert error.__cause__ is original_error


def test_creates_error_with_all_options():
    original_error = ValueError("Original")
    error = TJBotError(
        "Full error",
        code="FULL_ERROR",
        context={"field": "value"},
        cause=original_error,
    )
    assert error.code == "FULL_ERROR"
    assert error.context == {"field": "value"}
    assert error.cause is original_error


def test_error_can_be_thrown_and_caught():
    with pytest.raises(TJBotError, match="Throwable error"):
        raise TJBotError("Throwable error")


def test_error_is_an_instance_of_error():
    error = TJBotError("Test")
    assert isinstance(error, Exception)
    assert isinstance(error, TJBotError)


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


def test_has_stack_trace():
    try:
        raise TJBotError("Error with stack")
    except TJBotError as e:
        assert e.__traceback__ is not None


def test_maintains_stack_trace_through_chaining():
    cause = ValueError("Root cause")
    error = TJBotError("Chained error", cause=cause)
    assert error.cause is cause
    assert error.__cause__ is cause


def test_undefined_options_create_error_without_extra_properties():
    error = TJBotError("Simple error")
    assert error.code is None
    assert error.context is None
    assert error.cause is None
    assert str(error) == "Simple error"
