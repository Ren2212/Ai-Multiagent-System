from __future__ import annotations

import argparse
import os
import sys
import time
from typing import TextIO

from . import memory
from .color import Color
from .frontier import Frontier, FrontierBestFirst, FrontierBFS, FrontierDFS
from .graphsearch import search
from .heuristic import HeuristicAStar, HeuristicGreedy, HeuristicWeightedAStar
from .state import State


class SearchClient:
    @staticmethod
    def parse_level(server_messages: TextIO) -> State:
        # domain
        server_messages.readline()
        server_messages.readline()

        # level name
        server_messages.readline()
        server_messages.readline()

        # colors
        server_messages.readline()
        agent_colors: list[Color | None] = [None for _ in range(10)]
        box_colors: list[Color | None] = [None for _ in range(26)]

        line = server_messages.readline()
        while line and not line.startswith("#"):
            color_str, entities_str = line.split(":")
            color = Color.from_string(color_str.strip())

            for e in entities_str.split(","):
                e = e.strip()
                if "0" <= e <= "9":
                    agent_colors[ord(e) - ord("0")] = color
                elif "A" <= e <= "Z":
                    box_colors[ord(e) - ord("A")] = color

            line = server_messages.readline()

        # initial state
        level_lines: list[str] = []
        num_rows = 0
        num_cols = 0

        line = server_messages.readline()

        while line and not line.startswith("#"):
            s = line.rstrip("\r\n")
            level_lines.append(s)
            num_cols = max(num_cols, len(s))
            num_rows += 1
            line = server_messages.readline()

        walls = [[True for _ in range(num_cols)] for _ in range(num_rows)]
        boxes = [["" for _ in range(num_cols)] for _ in range(num_rows)]

        agent_rows = [-1 for _ in range(10)]
        agent_cols = [-1 for _ in range(10)]
        num_agents = 0

        for r, s in enumerate(level_lines):
            for c, ch in enumerate(s):

                if ch == "+":
                    walls[r][c] = True

                elif ch == " ":
                    walls[r][c] = False

                elif "0" <= ch <= "9":
                    walls[r][c] = False
                    agent_rows[ord(ch) - ord("0")] = r
                    agent_cols[ord(ch) - ord("0")] = c
                    num_agents += 1

                elif "A" <= ch <= "Z":
                    walls[r][c] = False
                    boxes[r][c] = ch

                else:
                    walls[r][c] = True

        del agent_rows[num_agents:]
        del agent_cols[num_agents:]

        goals = [["" for _ in range(num_cols)] for _ in range(num_rows)]

        line = server_messages.readline()
        row = 0

        while line and not line.startswith("#"):
            s = line.rstrip("\r\n")

            for col, ch in enumerate(s):
                if ("0" <= ch <= "9") or ("A" <= ch <= "Z"):
                    goals[row][col] = ch

            row += 1
            line = server_messages.readline()

        State.agent_colors = agent_colors
        State.box_colors = box_colors
        State.walls = walls
        State.goals = goals

        return State(agent_rows, agent_cols, boxes)

    @staticmethod
    def print_search_status(start_time: float, explored: set[State], frontier: Frontier) -> None:
        elapsed_time = time.perf_counter() - start_time

        print(
            f"#Expanded: {len(explored):8,}, "
            f"#Frontier: {frontier.size():8,}, "
            f"#Generated: {len(explored) + frontier.size():8,}, "
            f"Time: {elapsed_time:3.3f} s\n"
            f"[Alloc: {memory.get_usage():4.2f} MB, "
            f"MaxAlloc: {memory.max_usage:4.2f} MB]",
            file=sys.stderr,
            flush=True,
        )

    @staticmethod
    def _build_frontier(args: argparse.Namespace, state: State) -> Frontier:
        if getattr(args, "astar", False):
            return FrontierBestFirst(HeuristicAStar(state))
        if getattr(args, "wastar", False) is not False:
            return FrontierBestFirst(HeuristicWeightedAStar(state, args.wastar))
        if getattr(args, "greedy", False):
            return FrontierBestFirst(HeuristicGreedy(state))
        if getattr(args, "bfs", False):
            return FrontierBFS()
        if getattr(args, "dfs", False):
            return FrontierDFS()
        return FrontierBestFirst(HeuristicWeightedAStar(state, 5))

    @staticmethod
    def _clone_as_root(state: State) -> State:
        return State(
            state.agent_rows.copy(),
            state.agent_cols.copy(),
            [row.copy() for row in state.boxes],
        )

    @staticmethod
    def _unsolved_box_count(state: State) -> int:
        count = 0
        for r in range(len(state.boxes)):
            for c in range(len(state.boxes[r])):
                box = state.boxes[r][c]
                if box and State.goals[r][c] != box:
                    count += 1
        return count

    @staticmethod
    def _color_goals_satisfied(state: State, color: Color) -> bool:
        for r in range(len(State.goals)):
            for c in range(len(State.goals[r])):
                goal = State.goals[r][c]
                if not ("A" <= goal <= "Z"):
                    continue
                goal_color = State.box_colors[ord(goal) - ord("A")]
                if goal_color == color and state.boxes[r][c] != goal:
                    return False
        return True

    @staticmethod
    def _letter_goal_satisfied(state: State, letter: str) -> bool:
        for r in range(len(State.goals)):
            for c in range(len(State.goals[r])):
                if State.goals[r][c] == letter and state.boxes[r][c] != letter:
                    return False
        return True

    @staticmethod
    def _unsatisfied_letters_for_color(state: State, color: Color) -> list[str]:
        letters: list[str] = []
        for r in range(len(State.goals)):
            for c in range(len(State.goals[r])):
                goal = State.goals[r][c]
                if not ("A" <= goal <= "Z"):
                    continue
                goal_color = State.box_colors[ord(goal) - ord("A")]
                if goal_color != color:
                    continue
                if state.boxes[r][c] != goal and goal not in letters:
                    letters.append(goal)
        return letters

    @staticmethod
    def _agent_phase_priority(state: State, agent: int) -> int:
        color = State.agent_colors[agent]
        if color is None:
            return 10**9
        ar = state.agent_rows[agent]
        ac = state.agent_cols[agent]
        best = 10**9
        for r in range(len(state.boxes)):
            for c in range(len(state.boxes[r])):
                box = state.boxes[r][c]
                if not box:
                    continue
                if State.goals[r][c] == box:
                    continue
                box_color = State.box_colors[ord(box) - ord("A")]
                if box_color != color:
                    continue
                best = min(best, abs(ar - r) + abs(ac - c))
        return best

    @staticmethod
    def _should_use_phase_planning(args: argparse.Namespace, initial_state: State) -> bool:
        if getattr(args, "bfs", False) or getattr(args, "dfs", False):
            return False
        return len(initial_state.agent_rows) >= 3 and SearchClient._unsolved_box_count(initial_state) >= 10

    @staticmethod
    def _plan_with_phase_decomposition(
        args: argparse.Namespace,
        initial_state: State,
    ) -> list[list[Action]] | None:
        plan_prefix: list[list[Action]] = []
        state = initial_state

        agent_order = sorted(
            range(len(state.agent_rows)),
            key=lambda a: SearchClient._agent_phase_priority(state, a),
        )

        try:
            for agent in agent_order:
                color = State.agent_colors[agent]
                if color is None:
                    continue
                letters = SearchClient._unsatisfied_letters_for_color(state, color)
                if not letters:
                    continue

                State.ACTIVE_AGENT_IDS = {agent}
                for letter in letters:
                    phase_root = SearchClient._clone_as_root(state)
                    phase_weight = 15
                    phase_frontier: Frontier = FrontierBestFirst(
                        HeuristicWeightedAStar(phase_root, phase_weight)
                    )
                    phase_goal = (
                        lambda s, target_letter=letter: SearchClient._letter_goal_satisfied(
                            s, target_letter
                        )
                    )

                    print(
                        f"Phase solve for agent {agent} ({color.name}) letter {letter}.",
                        file=sys.stderr,
                        flush=True,
                    )
                    phase_plan = search(
                        phase_root,
                        phase_frontier,
                        goal_test=phase_goal,
                        max_expanded=40_000,
                    )

                    if phase_plan is None:
                        print(
                            f"Letter phase {letter} for agent {agent} did not finish; continuing.",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue

                    for joint_action in phase_plan:
                        state = state.result(joint_action)
                        plan_prefix.append(joint_action)
        finally:
            State.ACTIVE_AGENT_IDS = None

        if state.is_goal_state():
            return plan_prefix

        tail_root = SearchClient._clone_as_root(state)
        frontier = SearchClient._build_frontier(args, tail_root)
        tail_plan = search(tail_root, frontier)
        if tail_plan is not None:
            plan_prefix.extend(tail_plan)
            return plan_prefix

        # Return best-effort progress so GUI can show movement even when full solve
        # is not found within available time.
        if plan_prefix:
            return plan_prefix
        return None

    @staticmethod
    def main(args: argparse.Namespace) -> None:

        print("SearchClient initializing.", file=sys.stderr, flush=True)

        # send name to server
        client_name = args.name or os.environ.get("SEARCHCLIENT_NAME") or "SearchClient"
        print(client_name, flush=True)

        if args.max_memory is not None:
            memory.set_max_usage(float(args.max_memory))

        initial_state = SearchClient.parse_level(sys.stdin)

        if SearchClient._should_use_phase_planning(args, initial_state):
            print("Starting phased planning mode.", file=sys.stderr, flush=True)
            plan = SearchClient._plan_with_phase_decomposition(args, initial_state)
        else:
            frontier = SearchClient._build_frontier(args, initial_state)
            print(f"Starting {frontier.get_name()}.", file=sys.stderr, flush=True)
            plan = search(initial_state, frontier)

        if plan is None:
            print("Unable to solve level.", file=sys.stderr, flush=True)
            return

        print(f"Found solution of length {len(plan)}.", file=sys.stderr, flush=True)

        for joint_action in plan:
            print("|".join(a.name_ for a in joint_action), flush=True)
            _ = sys.stdin.readline()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Search client")

    group = parser.add_mutually_exclusive_group()

    group.add_argument("-astar", action="store_true")
    group.add_argument("-wastar", nargs="?", type=int, default=False, const=5)
    group.add_argument("-bfs", action="store_true")
    group.add_argument("-dfs", action="store_true")
    group.add_argument("-greedy", action="store_true")
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--max-memory", type=float, default=None)

    args = parser.parse_args()

    SearchClient.main(args)
