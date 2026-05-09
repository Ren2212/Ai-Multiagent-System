from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass

from .state import State


@dataclass(frozen=True)
class GoalCell:
    symbol: str  # '0'..'9' for agent goals, 'A'..'Z' for box goals
    row: int
    col: int


class Heuristic(ABC):
    """Heuristic base class.

    The assignment first asks you to implement a *goal-count* heuristic (Exercise 4.2),
    i.e., count how many goal cells are not satisfied.

    Later, you design an *improved* heuristic. This implementation provides:

      - goal-count heuristic (admissible but weak)
      - distance-based heuristic using precomputed *shortest-path* distances to goals

    The distance-based heuristic uses BFS on the static wall grid, which is cheap to
    precompute and typically much stronger than raw Manhattan distance.
    """

    # Toggle which heuristic to use.
    #   "goal_count"  : counts unsatisfied goal cells
    #   "goal_dist"   : sums shortest-path distances from objects to their goals
    HEURISTIC_MODE = "goal_dist"

    def __init__(self, initial_state: State) -> None:
        self.init_state = initial_state
        self.goal_cells: list[GoalCell] = []
        self._dist_from_cell: dict[tuple[int, int], list[list[int]]] = {}

        # Collect all goal cells.
        for r in range(len(State.goals)):
            for c in range(len(State.goals[r])):
                sym = State.goals[r][c]
                if sym:
                    self.goal_cells.append(GoalCell(sym, r, c))

        # Precompute shortest-path distances from each goal cell to all grid cells.
        # Distances ignore boxes/agents (dynamic obstacles), but account for walls.
        self._dist_from_goal: dict[tuple[int, int], list[list[int]]] = {}
        for g in self.goal_cells:
            self._dist_from_goal[(g.row, g.col)] = self._bfs_distance_map(g.row, g.col)

        # Index goal positions by symbol for quick lookup.
        self._agent_goal_pos: dict[int, tuple[int, int]] = {}
        self._box_goal_positions: dict[str, list[tuple[int, int]]] = {}
        for g in self.goal_cells:
            if "0" <= g.symbol <= "9":
                self._agent_goal_pos[ord(g.symbol) - ord("0")] = (g.row, g.col)
            elif "A" <= g.symbol <= "Z":
                self._box_goal_positions.setdefault(g.symbol, []).append((g.row, g.col))

    def h(self, state: State) -> int:
        cached = getattr(state, "_h_cache", None)
        if cached is not None:
            return cached

        if self.HEURISTIC_MODE == "goal_count":
            value = self._h_goal_count(state)
            state._h_cache = value  # type: ignore[attr-defined]
            return value
        if self.HEURISTIC_MODE == "goal_dist":
            value = self._h_goal_distance_sum(state)
            state._h_cache = value  # type: ignore[attr-defined]
            return value
        raise ValueError(f"Unknown HEURISTIC_MODE: {self.HEURISTIC_MODE}")

    # -----------------
    # Goal-count heuristic
    # -----------------
    def _h_goal_count(self, state: State) -> int:
        """Counts how many goal cells are not satisfied.

        - Agent goal cell 'i' is satisfied iff agent i stands on it.
        - Box goal cell 'X' is satisfied iff a box 'X' stands on it.
        """
        unsatisfied = 0
        for g in self.goal_cells:
            if "0" <= g.symbol <= "9":
                i = ord(g.symbol) - ord("0")
                if not (state.agent_rows[i] == g.row and state.agent_cols[i] == g.col):
                    unsatisfied += 1
            elif "A" <= g.symbol <= "Z":
                if state.boxes[g.row][g.col] != g.symbol:
                    unsatisfied += 1
        return unsatisfied

    # -----------------
    # Distance-based heuristic
    # -----------------
    def _h_goal_distance_sum(self, state: State) -> int:
        """A stronger heuristic for both MAPF and single-agent-with-boxes.

        MAPF part (agent goals):
          sum of shortest-path distances from each agent to its goal.

        Boxes part (box goals):
          for each box-goal cell, add distance from the *closest* matching box.

        Notes:
          - Distances ignore dynamic obstacles, so this is optimistic (underestimates)
            for A* in many cases; for greedy search it's still very effective guidance.
          - If a goal is unreachable in the static wall grid, we return a large penalty.
        """

        INF_PENALTY = 10**7
        DEADLOCK_PENALTY = 100_000

        deadlock_count = state.deadlock_count()
        if deadlock_count:
            return DEADLOCK_PENALTY * deadlock_count

        h_val = 0

        # 1) Agent goals.
        for agent_id, (ar, ac) in enumerate(zip(state.agent_rows, state.agent_cols)):
            if agent_id not in self._agent_goal_pos:
                continue
            gr, gc = self._agent_goal_pos[agent_id]
            dmap = self._dist_from_goal[(gr, gc)]
            d = dmap[ar][ac]
            if d < 0:
                return INF_PENALTY
            h_val += d

        # 2) Box goals.
        if self._box_goal_positions:
            # Collect current box positions by letter.
            curr_boxes: dict[str, list[tuple[int, int]]] = {}
            for r in range(len(state.boxes)):
                for c in range(len(state.boxes[r])):
                    b = state.boxes[r][c]
                    if b:
                        curr_boxes.setdefault(b, []).append((r, c))

            for box_letter, goal_positions in self._box_goal_positions.items():
                available_boxes = curr_boxes.get(box_letter, []).copy()
                if not available_boxes:
                    return INF_PENALTY

                ordered_goals = sorted(
                    goal_positions,
                    key=lambda goal: min(
                        (self._dist_from_goal[goal][br][bc] for (br, bc) in available_boxes),
                        default=INF_PENALTY,
                    ),
                )

                for (gr, gc) in ordered_goals:
                    dmap = self._dist_from_goal[(gr, gc)]
                    best = None
                    best_idx = None
                    for idx, (br, bc) in enumerate(available_boxes):
                        d = dmap[br][bc]
                        if d >= 0 and (best is None or d < best):
                            best = d
                            best_idx = idx
                    if best is None:
                        return INF_PENALTY
                    h_val += best
                    assert best_idx is not None
                    del available_boxes[best_idx]

            # Encourage agents to move toward useful boxes they can actually manipulate.
            for box_letter, boxes_of_type in curr_boxes.items():
                goals = self._box_goal_positions.get(box_letter)
                if not goals:
                    continue
                box_color = State.box_colors[ord(box_letter) - ord("A")]
                agent_positions = [
                    (state.agent_rows[i], state.agent_cols[i])
                    for i, color in enumerate(State.agent_colors[: len(state.agent_rows)])
                    if color == box_color
                ]
                if not agent_positions:
                    continue

                best_agent_box = None
                for br, bc in boxes_of_type:
                    if State.goals[br][bc] == box_letter:
                        continue
                    for ar, ac in agent_positions:
                        dist = self._distance_between(ar, ac, br, bc)
                        if dist < 0:
                            continue
                        if best_agent_box is None or dist < best_agent_box:
                            best_agent_box = dist
                if best_agent_box is not None:
                    h_val += best_agent_box // 2

        return h_val

    def _distance_from_cell(self, start_r: int, start_c: int) -> list[list[int]]:
        key = (start_r, start_c)
        if key not in self._dist_from_cell:
            self._dist_from_cell[key] = self._bfs_distance_map(start_r, start_c)
        return self._dist_from_cell[key]

    def _distance_between(self, start_r: int, start_c: int, goal_r: int, goal_c: int) -> int:
        dmap = self._distance_from_cell(start_r, start_c)
        return dmap[goal_r][goal_c]

    def _bfs_distance_map(self, start_r: int, start_c: int) -> list[list[int]]:
        """Compute shortest-path distances to (start_r, start_c) on the wall grid."""
        rows = len(State.walls)
        cols = len(State.walls[0])
        dist = [[-1 for _ in range(cols)] for _ in range(rows)]
        q: deque[tuple[int, int]] = deque()

        if State.walls[start_r][start_c]:
            return dist

        dist[start_r][start_c] = 0
        q.append((start_r, start_c))

        while q:
            r, c = q.popleft()
            nd = dist[r][c] + 1
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols and not State.walls[rr][cc] and dist[rr][cc] == -1:
                    dist[rr][cc] = nd
                    q.append((rr, cc))
        return dist

    @abstractmethod
    def f(self, state: State) -> int: ...

    @abstractmethod
    def __repr__(self) -> str: ...


class HeuristicAStar(Heuristic):
    def f(self, state: State) -> int:
        return state.g + self.h(state)

    def __repr__(self) -> str:
        return "A* evaluation"


class HeuristicWeightedAStar(Heuristic):
    def __init__(self, initial_state: State, w: int) -> None:
        super().__init__(initial_state)
        self.w = w

    def f(self, state: State) -> int:
        return state.g + self.w * self.h(state)

    def __repr__(self) -> str:
        return f"WA*({self.w}) evaluation"


class HeuristicGreedy(Heuristic):
    def f(self, state: State) -> int:
        return self.h(state)

    def __repr__(self) -> str:
        return "greedy evaluation"
