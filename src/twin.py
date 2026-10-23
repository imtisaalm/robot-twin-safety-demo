"""A small, deterministic 2D robot twin.

Units are metres and degrees. Heading 0 faces east; positive angles turn
counterclockwise. The robot is a point, not a body with a physical footprint.
Eight ideal range sensors are mounted at 45-degree intervals.

The simulation core uses only the Python standard library.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple


EPSILON = 1e-9


@dataclass(frozen=True)
class Box:
    """Axis-aligned obstacle, defined by its lower-left corner and size."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        values = (self.x, self.y, self.width, self.height)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Obstacle coordinates and dimensions must be finite.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Obstacle dimensions must be positive.")

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Return xmin, ymin, xmax, ymax."""
        return self.x, self.y, self.x + self.width, self.y + self.height


DEFAULT_OBSTACLES = (
    Box(4.2, 1.2, 1.3, 1.4),
    Box(6.5, 4.0, 1.5, 1.2),
    Box(2.8, 5.6, 1.2, 1.1),
    Box(8.2, 6.2, 0.9, 0.9),
)


def _ray_box_distance(
    x: float,
    y: float,
    dx: float,
    dy: float,
    bounds: Tuple[float, float, float, float],
) -> float:
    """Return distance to an AABB along a unit ray, or infinity if missed."""
    xmin, ymin, xmax, ymax = bounds
    near, far = -math.inf, math.inf

    for origin, direction, lower, upper in (
        (x, dx, xmin, xmax),
        (y, dy, ymin, ymax),
    ):
        if abs(direction) < EPSILON:
            if origin < lower or origin > upper:
                return math.inf
            continue

        first = (lower - origin) / direction
        second = (upper - origin) / direction
        near = max(near, min(first, second))
        far = min(far, max(first, second))

    if near > far:
        return math.inf

    if far < 0:
        return math.inf

    return max(0.0, near)


class RobotTwin:
    """Point robot in a rectangular room with immutable box obstacles.

    All forward movement goes through the safety policy in move_forward().
    Range readings are relative to the robot's heading. Public state
    properties are read-only.

    Args:
        x, y: Initial position strictly inside the room and outside obstacles.
        heading: Initial heading in degrees, normalized to [0, 360).
        width, height: Room dimensions in metres.
        obstacles: Box collection. None selects the four demo obstacles.
        safety_margin: Required forward clearance, in metres.
        step_size: Maximum distance between safety checks, in metres.
    """

    SENSOR_ANGLES = tuple(range(0, 360, 45))

    def __init__(
        self,
        x: float = 1.0,
        y: float = 1.0,
        heading: float = 0.0,
        width: float = 10.0,
        height: float = 8.0,
        obstacles: Optional[Tuple[Box, ...]] = None,
        safety_margin: float = 0.4,
        step_size: float = 0.05,
    ):
        values = (
            x, y, heading, width, height, safety_margin, step_size
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Robot and room parameters must be finite.")
        if width <= 0 or height <= 0:
            raise ValueError("Room dimensions must be positive.")
        if safety_margin <= 0 or step_size <= 0:
            raise ValueError("Safety margin and step size must be positive.")

        self._width = float(width)
        self._height = float(height)
        self._safety_margin = float(safety_margin)
        self._step_size = float(step_size)
        self._obstacles = tuple(
            DEFAULT_OBSTACLES if obstacles is None else obstacles
        )

        for obstacle in self._obstacles:
            xmin, ymin, xmax, ymax = obstacle.bounds
            if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
                raise ValueError("Every obstacle must fit inside the room.")

        if not (0 < x < width and 0 < y < height):
            raise ValueError("Initial position must be strictly inside the room.")
        for obstacle in self._obstacles:
            xmin, ymin, xmax, ymax = obstacle.bounds
            if xmin <= x <= xmax and ymin <= y <= ymax:
                raise ValueError("Initial position cannot touch an obstacle.")

        self._x = float(x)
        self._y = float(y)
        self._heading = float(heading) % 360.0
        self._distance_travelled = 0.0
        self._safety_events: List[dict] = []
        self._history: List[dict] = []
        self._record("start")

    @property
    def x(self) -> float:
        return self._x

    @property
    def y(self) -> float:
        return self._y

    @property
    def heading(self) -> float:
        return self._heading

    @property
    def width(self) -> float:
        return self._width

    @property
    def height(self) -> float:
        return self._height

    @property
    def safety_margin(self) -> float:
        return self._safety_margin

    @property
    def obstacles(self) -> Tuple[Box, ...]:
        return self._obstacles

    @property
    def history(self) -> List[dict]:
        """Return independent copies of recorded poses and events."""
        return [dict(frame) for frame in self._history]

    @property
    def safety_events(self) -> List[dict]:
        """Return independent copies of structured safety events."""
        return [dict(event) for event in self._safety_events]

    def snapshot(self) -> dict:
        """Return a JSON-compatible copy of the current state."""
        return {
            "x": self.x,
            "y": self.y,
            "heading": self.heading,
            "distance_travelled": self._distance_travelled,
            "safety_event_count": len(self._safety_events),
        }

    def _record(self, event: str):
        frame = self.snapshot()
        frame["event"] = event
        self._history.append(frame)

    def _range_at(self, relative_angle: float) -> float:
        angle = math.radians(self.heading + relative_angle)
        dx, dy = math.cos(angle), math.sin(angle)

        # Distance to the room boundary along this ray.
        distances = []
        if dx > EPSILON:
            distances.append((self.width - self.x) / dx)
        elif dx < -EPSILON:
            distances.append(-self.x / dx)
        if dy > EPSILON:
            distances.append((self.height - self.y) / dy)
        elif dy < -EPSILON:
            distances.append(-self.y / dy)

        distances.extend(
            _ray_box_distance(self.x, self.y, dx, dy, obstacle.bounds)
            for obstacle in self.obstacles
        )
        return max(0.0, min(distances))

    def sense(self) -> Dict[int, float]:
        """Return eight ideal ranges in metres, keyed by relative degrees.

        0 is forward, 90 is left, 180 is backward, and 270 is right.
        Every ray stops at its first obstacle or room wall.
        """
        return {
            angle: self._range_at(angle)
            for angle in self.SENSOR_ANGLES
        }

    def turn_left(self, degrees: float) -> dict:
        """Turn counterclockwise in place; return the resulting snapshot."""
        self._validate_nonnegative(degrees, "Turn angle")
        self._heading = (self.heading + degrees) % 360.0
        self._record("turn_left")
        return self.snapshot()

    def turn_right(self, degrees: float) -> dict:
        """Turn clockwise in place; return the resulting snapshot."""
        self._validate_nonnegative(degrees, "Turn angle")
        self._heading = (self.heading - degrees) % 360.0
        self._record("turn_right")
        return self.snapshot()

    @staticmethod
    def _validate_nonnegative(value: float, label: str):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{label} must be a finite, nonnegative number.")

    def move_forward(self, meters: float) -> dict:
        """Move forward with a clearance check before every incremental step.

        Steps are capped by both step_size and the exact forward clearance.
        This prevents tunnelling through even a thin obstacle with a large
        configured step size.

        An interrupted command logs a safety event and returns completed=False.
        The robot remains at least safety_margin from the surface ahead,
        subject to floating-point tolerance. An initial pose can already be
        closer than this margin; in that case forward movement is refused.

        Returns:
            requested, travelled, completed, and reason.
        """
        self._validate_nonnegative(meters, "Move distance")
        travelled = 0.0
        angle = math.radians(self.heading)
        dx, dy = math.cos(angle), math.sin(angle)

        while meters - travelled > EPSILON:
            forward_range = self.sense()[0]
            available = forward_range - self.safety_margin

            if available <= EPSILON:
                kind = "refused" if travelled <= EPSILON else "stopped"
                event = {
                    "kind": kind,
                    "x": self.x,
                    "y": self.y,
                    "heading": self.heading,
                    "forward_range": forward_range,
                    "safety_margin": self.safety_margin,
                    "requested": float(meters),
                    "travelled": travelled,
                    "message": (
                        f"Move {kind}: forward clearance "
                        f"{forward_range:.3f} m reached the "
                        f"{self.safety_margin:.3f} m safety margin."
                    ),
                }
                self._safety_events.append(event)
                self._record("safety_stop")
                return {
                    "requested": float(meters),
                    "travelled": travelled,
                    "completed": False,
                    "reason": event["message"],
                }

            step = min(self._step_size, meters - travelled, available)
            self._x += dx * step
            self._y += dy * step
            travelled += step
            self._distance_travelled += step
            self._record("move")

        return {
            "requested": float(meters),
            "travelled": travelled,
            "completed": True,
            "reason": "Requested distance completed.",
        }
