"""
Copyright 2025 IBM Corp. All Rights Reserved.
Copyright 2026-present TJBot Contributors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import shutil
import subprocess
import time
from typing import Optional, List, Dict, Any

# Try to import InquirerPy for better interactive prompts
try:
    from InquirerPy import inquirer
    HAS_INQUIRER = True
except ImportError:
    HAS_INQUIRER = False


def is_command_available(command: str) -> bool:
    """
    Check if a command-line tool is available in PATH

    Args:
        command: The command to check for

    Returns:
        True if command is available, false otherwise
    """
    return shutil.which(command) is not None


def prompt_user(question: str) -> str:
    """
    Prompt the user for input in an interactive test

    Args:
        question: The question to ask the user

    Returns:
        The user's response
    """
    return input(question).strip()


def sleep(seconds: float) -> None:
    """
    Sleep for a specified number of seconds

    Args:
        seconds: Seconds to sleep
    """
    time.sleep(seconds)


def confirm_user(question: str) -> bool:
    """
    Prompt user for yes/no confirmation

    Args:
        question: The question to ask

    Returns:
        True if user answered yes (or pressed enter), false if no
    """
    if HAS_INQUIRER:
        return inquirer.confirm(message=question, default=True).execute()

    answer = prompt_user(question).lower()
    return answer == '' or answer in ('yes', 'y')


def confirm(prompt: str) -> bool:
    """
    Ask user for confirmation (alias for confirm_user with different prompt style)

    Args:
        prompt: The prompt to display

    Returns:
        True if user confirmed, false otherwise
    """
    if HAS_INQUIRER:
        return inquirer.confirm(message=prompt, default=True).execute()

    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        print("Please answer 'y' or 'n'")


def prompt_input(message: str, default: str = "") -> str:
    """
    Prompt user for input with optional default

    Args:
        message: The message to display
        default: Optional default value

    Returns:
        User input or default value
    """
    if HAS_INQUIRER:
        return inquirer.text(message=message, default=default).execute()

    if default:
        response = input(f"{message} [{default}]: ").strip()
        return response if response else default
    return input(f"{message}: ").strip()


def select_option(message: str, choices: List[Dict[str, Any]], default: Optional[Any] = None) -> Any:
    """
    Prompt user to select from a list of options

    Args:
        message: The message to display
        choices: List of choice dictionaries with 'name' and 'value' keys
        default: Optional default value

    Returns:
        Selected value
    """
    if HAS_INQUIRER:
        return inquirer.select(
            message=message,
            choices=choices,
            default=default
        ).execute()

    # Fallback to simple numbered menu
    print(message)
    for i, choice in enumerate(choices, 1):
        name = choice.get('name', choice.get('value', str(choice)))
        print(f"  {i}. {name}")

    while True:
        response = input("Enter choice: ").strip()
        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx].get('value', choices[idx].get('name'))
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(choices)}")


def format_title(text: str) -> str:
    """
    Format text as a test title with decorative borders

    Args:
        text: The title text

    Returns:
        Formatted title string
    """
    line = "=" * (len(text) + 4)
    return f"\n{line}\n  {text}\n{line}\n"


def format_section(text: str) -> str:
    """
    Format text as a section header

    Args:
        text: The section text

    Returns:
        Formatted section header string
    """
    return f"\n{'─' * len(text)}\n{text}\n{'─' * len(text)}\n"


def is_module_available(module_name: str) -> bool:
    """
    Check if a Python module is available (can be imported)

    Args:
        module_name: Name of the module to check

    Returns:
        True if module is available, false otherwise
    """
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False
