"""Run with either:
    python tests/test_twin.py
    python -m pytest -q
"""

import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.prompt_control import CommandError, execute_prompt
from src.twin import Box, RobotTwin


def close(actual, expected):
    return math.isclose(actual, expected, abs_tol=1e-8)


def test_turn_math():
    twin = RobotTwin(obstacles=())
    twin.turn_left(450)
    assert close(twin.heading, 90)
    twin.turn_right(180)
    assert close(twin.heading, 270)
    twin.turn_right(630)
    assert close(twin.heading, 0)


def test_forward_motion():
    twin = RobotTwin(x=1, y=1, obstacles=())
    first = twin.move_forward(2)
    twin.turn_left(90)
    second = twin.move_forward(1.5)

    assert first["completed"]
    assert second["completed"]
    assert close(twin.x, 3)
    assert close(twin.y, 2.5)
    assert close(twin.snapshot()["distance_travelled"], 3.5)


def test_sensor_detects_wall_ahead():
    twin = RobotTwin(x=2, y=3, obstacles=())
    readings = twin.sense()

    assert len(readings) == 8
    assert close(readings[0], 8)
    assert close(readings[90], 5)
    assert close(readings[180], 2)
    assert close(readings[270], 3)

    twin.turn_left(90)
    assert close(twin.sense()[0], 5)


def test_safety_refusal_triggers():
    twin = RobotTwin(x=9.7, y=2, obstacles=())
    before = twin.snapshot()
    result = twin.move_forward(1)

    assert not result["completed"]
    assert close(result["travelled"], 0)
    assert close(twin.x, before["x"])
    assert close(twin.y, before["y"])
    assert len(twin.safety_events) == 1
    assert twin.safety_events[0]["kind"] == "refused"


def test_safety_stops_during_move():
    twin = RobotTwin(x=1, y=2)
    result = twin.move_forward(7)

    assert not result["completed"]
    assert close(result["travelled"], 2.8)
    assert close(twin.x, 3.8)
    assert close(twin.sense()[0], 0.4)
    assert twin.safety_events[0]["kind"] == "stopped"

    # Every recorded position remains on the safe side of the first obstacle.
    assert all(frame["x"] <= 3.8 + 1e-8 for frame in twin.history)


def test_large_step_cannot_tunnel_through_thin_obstacle():
    twin = RobotTwin(
        x=1,
        y=2,
        obstacles=(Box(3, 1, 0.01, 2),),
        step_size=100,
    )
    result = twin.move_forward(8)

    assert not result["completed"]
    assert close(twin.x, 2.6)
    assert close(twin.sense()[0], 0.4)


def test_diagonal_ray_hits_obstacle_corner():
    twin = RobotTwin(
        x=1,
        y=1,
        heading=45,
        obstacles=(Box(3, 3, 1, 1),),
    )
    assert close(twin.sense()[0], math.sqrt(8))
    result = twin.move_forward(5)

    assert not result["completed"]
    assert close(twin.sense()[0], 0.4)


def test_invalid_prompt_is_readable_and_atomic():
    twin = RobotTwin(obstacles=())
    before = twin.snapshot()

    try:
        execute_prompt(twin, "move forward 2 meters then teleport home")
    except CommandError as error:
        assert "Command 2" in str(error)
        assert "teleport home" in str(error)
    else:
        raise AssertionError("An unknown command must raise CommandError.")

    assert twin.snapshot() == before


def test_prompt_sequence_aborts_after_safety_stop():
    twin = RobotTwin(x=1, y=2)
    result = execute_prompt(
        twin, "move forward 7 meters, then turn left 90 degrees"
    )

    assert not result["completed"]
    assert result["commands_executed"] == 1
    assert result["commands_total"] == 2
    assert close(twin.heading, 0)


def test_clear_demo_route_completes():
    twin = RobotTwin()
    outcome = execute_prompt(
        twin,
        "move forward 2 meters, turn left 90 degrees, "
        "move forward 3 meters then turn right 90 degrees, "
        "move forward 2 meters.",
    )

    assert outcome["completed"]
    assert close(twin.x, 5)
    assert close(twin.y, 4)
    assert close(twin.snapshot()["distance_travelled"], 7)
    assert not twin.safety_events


def test_snapshot_and_history_are_independent_copies():
    twin = RobotTwin()
    snapshot = twin.snapshot()
    snapshot["x"] = 999
    history = twin.history
    history[0]["x"] = 999

    assert close(twin.x, 1)
    assert close(twin.history[0]["x"], 1)


if __name__ == "__main__":
    tests = sorted(
        (name, value)
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    for name, test in tests:
        test()
        print(f"PASS  {name}")
    print(f"\n{len(tests)} tests passed.")
