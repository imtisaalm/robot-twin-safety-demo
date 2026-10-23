"""Run two reproducible scenarios and render a plot and animated GIF.

Run from the project root:
    python src/run_demo.py

Output paths are resolved relative to this file, not the current directory.
"""

from pathlib import Path
import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

try:
    from .prompt_control import CommandError, execute_prompt
    from .twin import RobotTwin
except ImportError:
    from prompt_control import CommandError, execute_prompt
    from twin import RobotTwin


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

COLORS = {
    "page": "#F5F4F0",
    "room": "#FEFDF9",
    "ink": "#283B43",
    "muted": "#718087",
    "grid": "#DFE3E1",
    "obstacle": "#C5CCC9",
    "obstacle_edge": "#A4AEAA",
    "route": "#287F83",
    "start": "#49715B",
    "stop": "#BA6549",
}

SCENARIOS = (
    {
        "title": "01  /  Clear route",
        "subtitle": "Three moves, two turns, one completed route",
        "start": (1.0, 1.0),
        "prompt": (
            "move forward 2 meters, turn left 90 degrees, "
            "move forward 3 meters then turn right 90 degrees, "
            "move forward 2 meters"
        ),
    },
    {
        "title": "02  /  Safety intervention",
        "subtitle": "A direct approach stops before the obstacle",
        "start": (1.0, 2.0),
        "prompt": "move forward 7 meters",
    },
)


def configure_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": COLORS["ink"],
        "axes.labelcolor": COLORS["muted"],
        "xtick.color": COLORS["muted"],
        "ytick.color": COLORS["muted"],
        "figure.facecolor": COLORS["page"],
        "savefig.facecolor": COLORS["page"],
        "axes.facecolor": COLORS["room"],
    })


def run_scenarios():
    runs = []
    for spec in SCENARIOS:
        twin = RobotTwin(x=spec["start"][0], y=spec["start"][1])
        outcome = execute_prompt(twin, spec["prompt"])
        runs.append({
            "spec": spec,
            "twin": twin,
            "outcome": outcome,
            "frames": twin.history,
        })

    # These checks make failure to demonstrate safety a visible demo failure.
    first, second = runs
    if not first["outcome"]["completed"]:
        raise RuntimeError("Scenario 1 unexpectedly failed to complete.")
    if first["twin"].safety_events:
        raise RuntimeError("Scenario 1 unexpectedly triggered safety.")
    if second["outcome"]["completed"]:
        raise RuntimeError("Scenario 2 unexpectedly completed its unsafe move.")
    if not second["twin"].safety_events:
        raise RuntimeError("Scenario 2 did not produce a safety event.")
    if not math.isclose(
        second["twin"].sense()[0],
        second["twin"].safety_margin,
        abs_tol=1e-8,
    ):
        raise RuntimeError("Scenario 2 stopped at an unexpected clearance.")

    return runs


def draw_room(ax, run):
    twin, spec = run["twin"], run["spec"]

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.25, twin.width + 0.25)
    ax.set_ylim(-0.25, twin.height + 0.25)
    ax.set_xticks(range(0, 11, 2))
    ax.set_yticks(range(0, 9, 2))
    ax.set_xlabel("x / metres", labelpad=10)
    ax.set_ylabel("y / metres", labelpad=10)
    ax.tick_params(length=0, pad=7)
    ax.set_axisbelow(True)
    ax.grid(color=COLORS["grid"], linewidth=0.65, alpha=0.65)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.add_patch(Rectangle(
        (0, 0), twin.width, twin.height,
        fill=False, edgecolor=COLORS["ink"], linewidth=1.3, zorder=3,
    ))

    for obstacle in twin.obstacles:
        ax.add_patch(Rectangle(
            (obstacle.x, obstacle.y),
            obstacle.width,
            obstacle.height,
            facecolor=COLORS["obstacle"],
            edgecolor=COLORS["obstacle_edge"],
            linewidth=0.8,
            zorder=2,
        ))

    ax.set_title(
        spec["title"], loc="left", fontsize=15, fontweight="bold", pad=32
    )
    ax.text(
        0, 1.025, spec["subtitle"],
        transform=ax.transAxes, fontsize=9, color=COLORS["muted"],
    )

    start = run["frames"][0]
    ax.plot(
        start["x"], start["y"],
        marker="o", markersize=8,
        markerfacecolor=COLORS["room"],
        markeredgecolor=COLORS["start"],
        markeredgewidth=2,
        linestyle="none", zorder=6,
    )


def make_figure(runs, subtitle):
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7.3))
    fig.subplots_adjust(left=0.065, right=0.97, bottom=0.19, top=0.77, wspace=0.22)
    fig.text(
        0.065, 0.94, "ROBOT TWIN  /  PROMPT TO MOTION",
        fontsize=11, fontweight="bold", color=COLORS["route"],
    )
    fig.text(
        0.065, 0.885, subtitle, fontsize=20, fontweight="bold",
    )

    for ax, run in zip(axes, runs):
        draw_room(ax, run)

    handles = [
        Line2D(
            [0], [0], color=COLORS["route"], linewidth=2.5,
            label="Travelled route",
        ),
        Line2D(
            [0], [0], marker="o", linestyle="none",
            markerfacecolor=COLORS["room"],
            markeredgecolor=COLORS["start"], markeredgewidth=2,
            markersize=7, label="Start",
        ),
        Line2D(
            [0], [0], marker="s", linestyle="none",
            color=COLORS["route"], markersize=7, label="Completed",
        ),
        Line2D(
            [0], [0], marker="X", linestyle="none",
            color=COLORS["stop"], markersize=8, label="Safety stop",
        ),
    ]
    fig.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.065),
        ncol=4, frameon=False, columnspacing=2.5, handlelength=2,
    )
    fig.text(
        0.5, 0.035,
        "10 × 8 m room  •  8 ideal range sensors  •  0.40 m forward margin",
        ha="center", fontsize=9, color=COLORS["muted"],
    )
    return fig, axes


def save_trajectory(runs):
    fig, axes = make_figure(
        runs, "A clear route completes. An unsafe approach stops."
    )

    for ax, run in zip(axes, runs):
        frames = run["frames"]
        ax.plot(
            [frame["x"] for frame in frames],
            [frame["y"] for frame in frames],
            color=COLORS["route"], linewidth=2.7,
            solid_capstyle="round", zorder=4,
        )

        final = frames[-1]
        stopped = bool(run["twin"].safety_events)
        color = COLORS["stop"] if stopped else COLORS["route"]
        ax.plot(
            final["x"], final["y"], marker="X" if stopped else "s",
            color=color, markersize=10, linestyle="none", zorder=7,
        )

        if stopped:
            clearance = run["twin"].sense()[0]
            angle = math.radians(final["heading"])
            ax.plot(
                [final["x"], final["x"] + clearance * math.cos(angle)],
                [final["y"], final["y"] + clearance * math.sin(angle)],
                color=COLORS["stop"], linewidth=1.5, linestyle=":", zorder=5,
            )
            label = f"Safety stop\n{clearance:.2f} m clearance"
            offset = (-10, 48)
        else:
            label = "Route complete"
            offset = (0, 28)

        ax.annotate(
            label, (final["x"], final["y"]),
            xytext=offset, textcoords="offset points",
            ha="center", fontsize=10, color=color,
            bbox={
                "boxstyle": "round,pad=0.45",
                "facecolor": COLORS["room"],
                "edgecolor": "none",
                "alpha": 0.96,
            },
            arrowprops={"arrowstyle": "-", "color": color, "lw": 1},
            zorder=8,
        )
        ax.text(
            0.02, 0.96,
            f"Travelled {final['distance_travelled']:.2f} m",
            transform=ax.transAxes, va="top", fontsize=9,
            color=COLORS["muted"],
        )

    path = RESULTS / "trajectory.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def save_animation(runs):
    fig, axes = make_figure(
        runs, "Every forward step passes through the safety layer."
    )
    artists = []

    for ax, run in zip(axes, runs):
        start = run["frames"][0]
        trail, = ax.plot(
            [], [], color=COLORS["route"], linewidth=2.5, zorder=4,
        )
        robot = Circle(
            (start["x"], start["y"]), radius=0.11,
            facecolor=COLORS["route"], edgecolor=COLORS["room"],
            linewidth=1.4, zorder=7,
        )
        ax.add_patch(robot)
        heading, = ax.plot([], [], color=COLORS["ink"], linewidth=1.8, zorder=8)
        endpoint, = ax.plot([], [], linestyle="none", markersize=10, zorder=9)
        status = ax.text(
            0.02, 0.96, "", transform=ax.transAxes,
            va="top", fontsize=9, color=COLORS["muted"],
            bbox={
                "facecolor": COLORS["room"],
                "edgecolor": "none",
                "alpha": 0.9,
                "pad": 4,
            },
        )
        artists.append((trail, robot, heading, endpoint, status))

    longest = max(len(run["frames"]) for run in runs)
    hold_frames = 24

    def update(index):
        for run, items in zip(runs, artists):
            trail, robot, heading, endpoint, status = items
            frames = run["frames"]
            current_index = min(index, len(frames) - 1)
            current = frames[current_index]
            visible = frames[:current_index + 1]
            finished = current_index == len(frames) - 1
            stopped = current["event"] == "safety_stop"

            trail.set_data(
                [frame["x"] for frame in visible],
                [frame["y"] for frame in visible],
            )
            robot.center = (current["x"], current["y"])
            robot.set_facecolor(COLORS["stop"] if stopped else COLORS["route"])

            angle = math.radians(current["heading"])
            heading.set_data(
                [current["x"], current["x"] + 0.35 * math.cos(angle)],
                [current["y"], current["y"] + 0.35 * math.sin(angle)],
            )

            if finished:
                endpoint.set_data([current["x"]], [current["y"]])
                endpoint.set_marker("X" if stopped else "s")
                endpoint.set_color(COLORS["stop"] if stopped else COLORS["route"])
                state = "SAFETY STOP" if stopped else "COMPLETE"
            else:
                endpoint.set_data([], [])
                state = "TURNING" if current["event"].startswith("turn") else "MOVING"

            message = f"{state}  /  {current['distance_travelled']:.2f} m travelled"
            if stopped:
                message += f"  /  {run['twin'].sense()[0]:.2f} m clearance"
            status.set_text(message)
            status.set_color(COLORS["stop"] if stopped else COLORS["muted"])

        return [artist for group in artists for artist in group]

    animation = FuncAnimation(
        fig, update, frames=longest + hold_frames,
        interval=1000 / 20, blit=False, repeat=True,
    )
    path = RESULTS / "demo.gif"
    animation.save(path, writer=PillowWriter(fps=20), dpi=100)
    plt.close(fig)
    return path


def main():
    configure_style()
    RESULTS.mkdir(parents=True, exist_ok=True)

    try:
        runs = run_scenarios()
    except CommandError as error:
        print(f"Command error: {error}")
        return 2

    for run in runs:
        twin = run["twin"]
        state = twin.snapshot()
        print(f"\n{run['spec']['title']}")
        print(f" Prompt: {run['spec']['prompt']}")
        print(f" Completed: {run['outcome']['completed']}")
        print(f" Distance: {state['distance_travelled']:.3f} m")
        print(
            f" Final pose: ({state['x']:.3f}, {state['y']:.3f}), "
            f"heading {state['heading']:.1f} degrees"
        )
        print(f" Safety events: {state['safety_event_count']}")
        for event in twin.safety_events:
            print(f" SAFETY: {event['message']}")

    print(f"\nSaved {save_trajectory(runs)}")
    print(f"Saved {save_animation(runs)}")
    print("Animation frames show simulation steps, not physical elapsed time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
