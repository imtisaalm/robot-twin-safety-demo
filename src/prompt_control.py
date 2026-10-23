"""A deliberately small, deterministic English command interface.

This is a parser, not an LLM. It accepts an explicit grammar and rejects
everything else before executing any part of a prompt.
"""

import re
from typing import List, Tuple

try:
    from .twin import RobotTwin
except ImportError:
    from twin import RobotTwin


class CommandError(ValueError):
    """Readable validation error for an unsupported or malformed command."""


NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"

PATTERNS = (
    (
        "move_forward",
        re.compile(
            rf"move\s+forward\s+({NUMBER})\s+(?:meters?|metres?|m)",
            re.IGNORECASE,
        ),
    ),
    (
        "turn_left",
        re.compile(
            rf"turn\s+left\s+({NUMBER})\s+(?:degrees?|deg)",
            re.IGNORECASE,
        ),
    ),
    (
        "turn_right",
        re.compile(
            rf"turn\s+right\s+({NUMBER})\s+(?:degrees?|deg)",
            re.IGNORECASE,
        ),
    ),
)

SEPARATOR = re.compile(r"\s*(?:,\s*(?:then\b)?|\bthen\b)\s*", re.IGNORECASE)


def parse_commands(prompt: str) -> List[Tuple[str, float]]:
    """Validate the entire prompt and return method-name/value pairs.

    Commands may be separated by commas, 'then', or ', then'.
    A single final full stop is optional. Distances and angles must be
    finite, nonnegative decimal numbers.

    Raises:
        CommandError: If any command is empty, unknown, or malformed.
    """
    import math

    if not isinstance(prompt, str) or not prompt.strip():
        raise CommandError("Enter at least one movement or turn command.")

    text = prompt.strip()
    if text.endswith("."):
        text = text[:-1].rstrip()

    commands = []
    for index, part in enumerate(SEPARATOR.split(text), start=1):
        part = part.strip()
        if not part:
            raise CommandError(
                f"Command {index} is empty. Remove the extra separator."
            )

        for method_name, pattern in PATTERNS:
            match = pattern.fullmatch(part)
            if match:
                value = float(match.group(1))
                if not math.isfinite(value):
                    raise CommandError(
                        f"Command {index} contains a number that is too large."
                    )
                commands.append((method_name, value))
                break
        else:
            raise CommandError(
                f"Command {index} is not supported: {part!r}. "
                "Use 'move forward 2 meters', 'turn left 90 degrees', "
                "or 'turn right 45 degrees'."
            )

    return commands


def execute_prompt(twin: RobotTwin, prompt: str) -> dict:
    """Validate, then execute commands in order through the twin API.

    A safety refusal or stop aborts the remaining command sequence.
    Invalid prompts raise CommandError before any movement occurs.

    Returns:
        completed, commands_executed, commands_total, and results.
    """
    commands = parse_commands(prompt)
    results = []

    for method_name, value in commands:
        result = getattr(twin, method_name)(value)
        results.append({
            "command": method_name,
            "value": value,
            "result": result,
        })
        if method_name == "move_forward" and not result["completed"]:
            return {
                "completed": False,
                "commands_executed": len(results),
                "commands_total": len(commands),
                "results": results,
            }

    return {
        "completed": True,
        "commands_executed": len(results),
        "commands_total": len(commands),
        "results": results,
    }
