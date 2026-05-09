#!/usr/bin/env python3
import argparse
import re
import sys
from typing import List

# Stable interactive backend
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from searchclient.state import State

# Level parsing (static)
def parse_level(path: str):
    """
    Parse a .lvl file:
      - '#' walls
      - digits 0..9 agents
      - 'A'..'Z' boxes
      - 'a'..'z' goals (stored as uppercase for drawing)
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if not l.startswith(";")]

    H = len(lines)
    W = max(len(l) for l in lines)

    walls = [[False] * W for _ in range(H)]
    goals = [[""] * W for _ in range(H)]
    boxes = [[""] * W for _ in range(H)]
    agent_rows, agent_cols = [], []

    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == "#":
                walls[r][c] = True
            elif ch.isdigit():
                agent_rows.append(r)
                agent_cols.append(c)
            elif ch.isupper():
                boxes[r][c] = ch
            elif ch.islower():
                goals[r][c] = ch.upper()

    return walls, goals, agent_rows, agent_cols, boxes

# Plan/log parsing
MOVE_DELTA = {
    "Move(N)": (-1, 0),
    "Move(S)": (1, 0),
    "Move(W)": (0, -1),
    "Move(E)": (0, 1),
    "NoOp": (0, 0),
}

ACTION_RE = re.compile(
    r"(Move\s*\(\s*[NSEW]\s*\)|NoOp|Push\s*\(\s*[NSEW]\s*,\s*[NSEW]\s*\)|Pull\s*\(\s*[NSEW]\s*,\s*[NSEW]\s*\))",
    flags=re.IGNORECASE
)

def normalize_action(a: str) -> str:
    """
    Normalize many possible action formats to one of:
      Move(N), Move(S), Move(E), Move(W), NoOp
    Also recognizes Push/Pull tokens but (for now) treats them as NoOp in simulation
    unless you later extend box dynamics.
    """
    a = a.strip()
    # strip common punctuation/containers
    a = a.strip(",;|[]{}")

    if not a:
        return "NoOp"

    # canonicalize casing
    upper = a.upper()

    alias = {
        "NOOP": "NoOp",
        "NOP": "NoOp",
        "WAIT": "NoOp",
        "STOP": "NoOp",
        "N": "Move(N)",
        "S": "Move(S)",
        "E": "Move(E)",
        "W": "Move(W)",
        "UP": "Move(N)",
        "DOWN": "Move(S)",
        "LEFT": "Move(W)",
        "RIGHT": "Move(E)",
    }
    if upper in alias:
        return alias[upper]

    # already canonical
    if a in ("NoOp", "Move(N)", "Move(S)", "Move(E)", "Move(W)"):
        return a

    # Match Move(X)
    m = re.search(r"Move\s*\(\s*([NSEW])\s*\)", a, flags=re.IGNORECASE)
    if m:
        return f"Move({m.group(1).upper()})"

    # Push/Pull are recognized but require box simulation to animate correctly.
    # For now, we allow them in input but treat as NoOp to avoid crashing.
    if re.search(r"Push\s*\(", a, flags=re.IGNORECASE):
        return "NoOp"
    if re.search(r"Pull\s*\(", a, flags=re.IGNORECASE):
        return "NoOp"

    return "NoOp"


def parse_plan_or_log(path: str) -> List[List[str]]:
    """
    Accepts either:
      - a proper plan file (one action line per timestep), OR
      - a server/client log (contains noise + maybe action lines)

    Returns a list of timesteps, where each timestep is a list of action tokens.
    """
    steps: List[List[str]] = []
    raw_action_lines = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Extract action tokens anywhere on the line
            found = ACTION_RE.findall(line)
            if not found:
                # Also support joint-action lines separated by spaces or pipes that contain Move/NoOp
                # e.g. "Move(E)|NoOp|Move(N)"
                if "Move" in line or "NoOp" in line or "Push" in line or "Pull" in line:
                    # Split on pipes and whitespace, then keep plausible tokens
                    tokens = re.split(r"[|\s]+", line)
                    tokens = [t for t in tokens if ACTION_RE.search(t)]
                    if tokens:
                        found = tokens

            if found:
                raw_action_lines += 1
                # Normalize each token
                norm = [normalize_action(tok) for tok in found]
                steps.append(norm)

    if raw_action_lines == 0:
        # This is a pure summary log
        raise ValueError(
            f"No action lines found in '{path}'.\n\n"
            "This file looks like a server/client SUMMARY log (Level solved / Actions used / Time to solve),\n"
            "which is not enough to animate movement. The visualizer needs the PLAN: one timestep per line, e.g.\n"
            "  Move(E)\n  Move(S)\n  ...\n\n"
            "How to generate a plan file (capture client stdout):\n"
            "  java -jar ../server.jar -l ../levels/MAPF00.lvl -c \"python3 main.py -bfs\" -s 200 \\\n"
            "    2> server_MAPF00.log | tee plan_MAPF00.txt\n\n"
            "Then run:\n"
            "  python3 visualize.py -l ../levels/MAPF00.lvl -p plan_MAPF00.txt\n"
        )

    return steps

# Simulation (agents only)
def simulate_agents_only(agent_rows, agent_cols, boxes, plan_steps):
    """
    Build timeline of State snapshots by applying agent moves.
    Works for both:
      - single-agent plan: 1 token per timestep
      - multi-agent plan:  N tokens per timestep

    If timestep token-count != n_agents, we treat it as single-agent (agent 0),
    and others NoOp.
    """
    timeline = []
    r = agent_rows[:]
    c = agent_cols[:]
    n_agents = len(r)

    timeline.append(State(r[:], c[:], boxes))

    for step in plan_steps:
        if len(step) != n_agents:
            actions = ["NoOp"] * n_agents
            actions[0] = step[0] if step else "NoOp"
        else:
            actions = step

        for i, act in enumerate(actions):
            dr, dc = MOVE_DELTA.get(act, (0, 0))
            r[i] += dr
            c[i] += dc

        timeline.append(State(r[:], c[:], boxes))

    return timeline

# Visualizer
class Visualizer:
    def __init__(self, walls, goals, timeline, interval_ms=250):
        self.walls = walls
        self.goals = goals
        self.timeline = timeline
        self.t = 0
        self.playing = False
        self.interval_ms = interval_ms

        self.fig, self.ax = plt.subplots()
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.anim = None  # keep reference

    def on_key(self, event):
        if event.key == " ":
            self.playing = not self.playing
            self.redraw()
        elif event.key == "right":
            self.step(1)
        elif event.key == "left":
            self.step(-1)

    def step(self, delta):
        self.t = max(0, min(len(self.timeline) - 1, self.t + delta))
        self.redraw()

    def redraw(self):
        self.ax.clear()
        state = self.timeline[self.t]
        H, W = len(self.walls), len(self.walls[0])

        # Draw grid & walls
        for r in range(H):
            for c in range(W):
                if self.walls[r][c]:
                    self.ax.add_patch(plt.Rectangle((c, H - r - 1), 1, 1, color="black"))
                else:
                    self.ax.add_patch(
                        plt.Rectangle(
                            (c, H - r - 1), 1, 1,
                            facecolor="#eeeeee",
                            edgecolor="#cccccc",
                            linewidth=0.5
                        )
                    )

        # Draw goals
        for r in range(H):
            for c in range(W):
                if self.goals[r][c]:
                    self.ax.add_patch(
                        plt.Rectangle(
                            (c + 0.15, H - r - 1 + 0.15), 0.7, 0.7,
                            facecolor="#f3f3a0",
                            edgecolor="#999900"
                        )
                    )

        # Draw boxes (static unless you later implement Push/Pull)
        for r in range(H):
            for c in range(W):
                b = state.boxes[r][c]
                if b:
                    self.ax.add_patch(
                        plt.Rectangle(
                            (c + 0.1, H - r - 1 + 0.1), 0.8, 0.8,
                            facecolor="#b0b0b0",
                            edgecolor="#444444"
                        )
                    )
                    self.ax.text(
                        c + 0.5, H - r - 0.5, b,
                        ha="center", va="center",
                        fontsize=10, fontweight="bold", color="black"
                    )

        # Draw agents
        for i, (r, c) in enumerate(zip(state.agent_rows, state.agent_cols)):
            self.ax.add_patch(plt.Circle((c + 0.5, H - r - 0.5), 0.33, color="#2aa6c9"))
            self.ax.text(
                c + 0.5, H - r - 0.5, str(i),
                ha="center", va="center",
                color="white", fontweight="bold"
            )

        self.ax.set_xlim(0, W)
        self.ax.set_ylim(0, H)
        self.ax.set_aspect("equal")
        self.ax.axis("off")

        status = "PLAY" if self.playing else "PAUSE"
        self.ax.set_title(
            f"t = {self.t}/{len(self.timeline) - 1}  [{status}]   (Space=Play/Pause, ←/→=Step)"
        )
        plt.draw()

    def tick(self, _):
        if self.playing and self.t < len(self.timeline) - 1:
            self.t += 1
            self.redraw()
        return []

    def run(self):
        self.redraw()
        # cache_frame_data=False avoids frame-cache warning
        self.anim = animation.FuncAnimation(
            self.fig, self.tick, interval=self.interval_ms, cache_frame_data=False
        )
        plt.show()


# Main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-l", "--level", required=True, help="Path to .lvl file")
    ap.add_argument(
        "-p", "--plan", required=True,
        help="Plan file OR log file. If it is a log, it must contain action lines (Move/NoOp/Push/Pull)."
    )
    ap.add_argument("--interval", type=int, default=250, help="Animation interval in ms")
    args = ap.parse_args()

    walls, goals, agent_rows, agent_cols, boxes = parse_level(args.level)

    try:
        plan_steps = parse_plan_or_log(args.plan)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    timeline = simulate_agents_only(agent_rows, agent_cols, boxes, plan_steps)

    vis = Visualizer(walls, goals, timeline, interval_ms=args.interval)
    vis.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

