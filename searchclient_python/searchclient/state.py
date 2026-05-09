from __future__ import annotations

import random
from typing import ClassVar

from .action import Action, ActionType
from .color import Color


class State:
    _RNG = random.Random(1)
    LARGE_DISTANCE: ClassVar[int] = 10**9
    JOINT_ACTION_MODE: ClassVar[str] = "sequential"
    ACTIVE_AGENT_IDS: ClassVar[set[int] | None] = None
    ENABLE_ACTION_PRUNING: ClassVar[bool] = True
    MAX_ACTIVE_AGENTS: ClassVar[int] = 2
    MAX_MOVE_ACTIONS_PER_AGENT: ClassVar[int] = 2
    # The warmup domain supports Pull actions, so classic Sokoban static deadlock
    # rules (corners/corridors/2x2) are not generally sound. Keep pruning off by default.
    ENABLE_STATIC_DEADLOCK_PRUNING: ClassVar[bool] = False

    agent_colors: ClassVar[list[Color | None]]
    walls: ClassVar[list[list[bool]]]
    box_colors: ClassVar[list[Color | None]]
    goals: ClassVar[list[list[str]]]

    def __init__(self, agent_rows: list[int], agent_cols: list[int], boxes: list[list[str]]) -> None:
        self.agent_rows = agent_rows
        self.agent_cols = agent_cols
        self.boxes = boxes

        self.parent: State | None = None
        self.joint_action: list[Action] | None = None
        self.g = 0

    # ----------------- Bounds -----------------

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < len(State.walls) and 0 <= c < len(State.walls[0])

    def agent_at(self, r: int, c: int) -> str | None:
        if not self.in_bounds(r, c):
            return None
        for a, (ar, ac) in enumerate(zip(self.agent_rows, self.agent_cols)):
            if ar == r and ac == c:
                return str(a)
        return None

    def is_free(self, r: int, c: int) -> bool:
        if not self.in_bounds(r, c):
            return False
        return (not State.walls[r][c]) and self.boxes[r][c] == "" and self.agent_at(r, c) is None

    def _box_at(self, r: int, c: int) -> str | None:
        if not self.in_bounds(r, c):
            return None
        box = self.boxes[r][c]
        return box if box else None

    @staticmethod
    def _is_box_goal_symbol(symbol: str) -> bool:
        return "A" <= symbol <= "Z"

    @staticmethod
    def _goal_matches_box(goal_symbol: str, box_symbol: str) -> bool:
        return goal_symbol == box_symbol

    def _cell_has_matching_goal(self, r: int, c: int, box_symbol: str) -> bool:
        return self._goal_matches_box(State.goals[r][c], box_symbol)

    def _row_has_goal_for(self, row: int, box_symbol: str) -> bool:
        return any(self._goal_matches_box(goal, box_symbol) for goal in State.goals[row])

    def _col_has_goal_for(self, col: int, box_symbol: str) -> bool:
        return any(self._goal_matches_box(State.goals[r][col], box_symbol) for r in range(len(State.goals)))

    def _is_static_deadlock(self, r: int, c: int) -> bool:
        box = self._box_at(r, c)
        if box is None:
            return False

        if self._cell_has_matching_goal(r, c, box):
            return False

        up = State.walls[r - 1][c] if r > 0 else True
        down = State.walls[r + 1][c] if r + 1 < len(State.walls) else True
        left = State.walls[r][c - 1] if c > 0 else True
        right = State.walls[r][c + 1] if c + 1 < len(State.walls[r]) else True

        if (up or down) and (left or right):
            return True

        if left and right and not self._col_has_goal_for(c, box):
            return True

        if up and down and not self._row_has_goal_for(r, box):
            return True

        if self._forms_deadlock_block(r, c, box):
            return True

        return False

    def _forms_deadlock_block(self, r: int, c: int, box_symbol: str) -> bool:
        for dr in (-1, 0):
            for dc in (-1, 0):
                cells = [
                    (r + dr, c + dc),
                    (r + dr + 1, c + dc),
                    (r + dr, c + dc + 1),
                    (r + dr + 1, c + dc + 1),
                ]
                if not all(self.in_bounds(rr, cc) for rr, cc in cells):
                    continue

                blocked = 0
                has_non_goal_box = False
                for rr, cc in cells:
                    if State.walls[rr][cc]:
                        blocked += 1
                        continue

                    cell_box = self._box_at(rr, cc)
                    if cell_box is None:
                        continue

                    blocked += 1
                    if not self._cell_has_matching_goal(rr, cc, cell_box):
                        has_non_goal_box = True

                if blocked == 4 and has_non_goal_box:
                    return True

        return False

    def has_deadlock(self) -> bool:
        if not State.ENABLE_STATIC_DEADLOCK_PRUNING:
            return False
        return self.deadlock_count() > 0

    def deadlock_count(self) -> int:
        if not State.ENABLE_STATIC_DEADLOCK_PRUNING:
            return 0
        count = 0
        for r in range(len(self.boxes)):
            for c in range(len(self.boxes[r])):
                if self._is_static_deadlock(r, c):
                    count += 1
        return count

    # ----------------- Goal -----------------

    def is_goal_state(self) -> bool:
        for r in range(len(State.goals)):
            for c in range(len(State.goals[r])):
                g = State.goals[r][c]
                if g == "":
                    continue
                if "A" <= g <= "Z":
                    if self.boxes[r][c] != g:
                        return False
                elif "0" <= g <= "9":
                    if self.agent_at(r, c) != g:
                        return False
        return True

    # ----------------- Expansion (STRICT) -----------------

    def _collect_unsolved_boxes_by_color(self) -> dict[Color, list[tuple[int, int]]]:
        unsolved: dict[Color, list[tuple[int, int]]] = {}
        for r in range(len(self.boxes)):
            for c in range(len(self.boxes[r])):
                box = self.boxes[r][c]
                if not box:
                    continue
                if State.goals[r][c] == box:
                    continue
                color = State.box_colors[ord(box) - ord("A")]
                if color is None:
                    continue
                unsolved.setdefault(color, []).append((r, c))
        return unsolved

    @staticmethod
    def _manhattan_to_nearest(r: int, c: int, targets: list[tuple[int, int]]) -> int:
        if not targets:
            return State.LARGE_DISTANCE
        return min(abs(r - tr) + abs(c - tc) for tr, tc in targets)

    def _agent_task_distance(
        self,
        agent: int,
        unsolved_boxes_by_color: dict[Color, list[tuple[int, int]]],
    ) -> int:
        color = State.agent_colors[agent]
        if color is None:
            return State.LARGE_DISTANCE
        targets = unsolved_boxes_by_color.get(color, [])
        if not targets:
            return State.LARGE_DISTANCE
        return self._manhattan_to_nearest(self.agent_rows[agent], self.agent_cols[agent], targets)

    def _filter_actions_for_agent(
        self,
        agent: int,
        actions: list[Action],
        unsolved_boxes_by_color: dict[Color, list[tuple[int, int]]],
    ) -> list[Action]:
        if not actions:
            return actions

        box_actions = [a for a in actions if a.type in (ActionType.Push, ActionType.Pull)]
        move_actions = [a for a in actions if a.type == ActionType.Move]

        color = State.agent_colors[agent]
        targets = unsolved_boxes_by_color.get(color, []) if color is not None else []

        if not targets:
            if box_actions:
                return box_actions
            return move_actions[:1]

        ar = self.agent_rows[agent]
        ac = self.agent_cols[agent]
        current_dist = self._manhattan_to_nearest(ar, ac, targets)

        move_scores: list[tuple[int, Action]] = []
        for action in move_actions:
            nr = ar + action.agent_row_delta
            nc = ac + action.agent_col_delta
            move_scores.append((self._manhattan_to_nearest(nr, nc, targets), action))

        improving_moves = [a for d, a in move_scores if d < current_dist]
        move_scores.sort(key=lambda item: item[0])

        if box_actions:
            selected = box_actions.copy()
            if improving_moves:
                selected.extend(improving_moves[:1])
            elif move_scores:
                selected.append(move_scores[0][1])
            return selected

        if improving_moves:
            return improving_moves[: State.MAX_MOVE_ACTIONS_PER_AGENT]
        return [a for _, a in move_scores[: State.MAX_MOVE_ACTIONS_PER_AGENT]]

    def get_expanded_states(self) -> list["State"]:
        """
        Generates ONLY valid successor states.
        For MAPF00 (single agent), this is straightforward.
        For multi-agent levels, this still builds joint actions but only from applicable actions.
        """
        num_agents = len(self.agent_rows)

        # Applicable actions per agent (filter first!)
        applicable: list[list[Action]] = []
        for agent in range(num_agents):
            acts = [a for a in Action if self.is_applicable(agent, a)]
            applicable.append(acts)

        unsolved_boxes_by_color: dict[Color, list[tuple[int, int]]] = {}
        enable_multi_agent_pruning = State.ENABLE_ACTION_PRUNING and num_agents > 1
        if enable_multi_agent_pruning:
            unsolved_boxes_by_color = self._collect_unsolved_boxes_by_color()
            unsolved_box_count = sum(len(v) for v in unsolved_boxes_by_color.values())
            # Keep search complete and broad on small levels; use pruning only where
            # branching is the primary bottleneck.
            if unsolved_box_count <= 8:
                enable_multi_agent_pruning = False

        # Single-agent fast path (MAPF00)
        if num_agents == 1:
            expanded = []
            for action in applicable[0]:
                child = self.result([action])
                if not child.has_deadlock():
                    expanded.append(child)
            State._RNG.shuffle(expanded)
            return expanded

        expanded: list[State] = []

        if State.JOINT_ACTION_MODE == "sequential":
            agent_indices = list(range(num_agents))
            if State.ACTIVE_AGENT_IDS is not None:
                agent_indices = [a for a in agent_indices if a in State.ACTIVE_AGENT_IDS]

            if enable_multi_agent_pruning:
                ranked_agents = sorted(
                    agent_indices,
                    key=lambda a: self._agent_task_distance(a, unsolved_boxes_by_color),
                )
                max_agents = max(1, min(State.MAX_ACTIVE_AGENTS, num_agents))
                selected_agents = ranked_agents[:max_agents]
                rotating_agent = self.g % num_agents
                if rotating_agent not in selected_agents:
                    selected_agents.append(rotating_agent)
                agent_indices = selected_agents

            for agent in agent_indices:
                agent_actions = applicable[agent]
                if enable_multi_agent_pruning:
                    agent_actions = self._filter_actions_for_agent(
                        agent, agent_actions, unsolved_boxes_by_color
                    )

                for action in agent_actions:
                    if action.type == ActionType.NoOp:
                        continue
                    joint_action = [Action.NoOp for _ in range(num_agents)]
                    joint_action[agent] = action
                    child = self.result(joint_action)
                    if not child.has_deadlock():
                        expanded.append(child)
        else:
            joint_action = [Action.NoOp for _ in range(num_agents)]
            perm = [0 for _ in range(num_agents)]
            while True:
                for i in range(num_agents):
                    joint_action[i] = applicable[i][perm[i]]

                if not self.is_conflicting(joint_action):
                    child = self.result(joint_action)
                    if not child.has_deadlock():
                        expanded.append(child)

                i = 0
                while i < num_agents:
                    perm[i] += 1
                    if perm[i] < len(applicable[i]):
                        break
                    perm[i] = 0
                    i += 1
                if i == num_agents:
                    break

        State._RNG.shuffle(expanded)
        return expanded

    # ----------------- Applicability -----------------

    def is_applicable(self, agent: int, action: Action) -> bool:
        ar = self.agent_rows[agent]
        ac = self.agent_cols[agent]

        if action.type == ActionType.NoOp:
            return True

        if action.type == ActionType.Move:
            return self.is_free(ar + action.agent_row_delta, ac + action.agent_col_delta)

        if action.type == ActionType.Push:
            br = ar + action.agent_row_delta
            bc = ac + action.agent_col_delta
            if not self.in_bounds(br, bc):
                return False
            box = self._box_at(br, bc)
            if box is None:
                return False
            if State.box_colors[ord(box) - ord("A")] != State.agent_colors[agent]:
                return False
            return self.is_free(br + action.box_row_delta, bc + action.box_col_delta)

        if action.type == ActionType.Pull:
            nr = ar + action.agent_row_delta
            nc = ac + action.agent_col_delta
            if not self.is_free(nr, nc):
                return False
            # For Pull(X,Y), Y is the movement direction of the box.
            # The source box must therefore be located opposite Y from the agent.
            br = ar - action.box_row_delta
            bc = ac - action.box_col_delta
            if not self.in_bounds(br, bc):
                return False
            box = self._box_at(br, bc)
            if box is None:
                return False
            if State.box_colors[ord(box) - ord("A")] != State.agent_colors[agent]:
                return False
            return True

        return False

    # ----------------- Successor -----------------

    def result(self, joint_action: list[Action]) -> "State":
        rows = self.agent_rows.copy()
        cols = self.agent_cols.copy()
        boxes = [r.copy() for r in self.boxes]

        for a, act in enumerate(joint_action):
            if act.type == ActionType.NoOp:
                continue

            if act.type == ActionType.Move:
                rows[a] += act.agent_row_delta
                cols[a] += act.agent_col_delta

            elif act.type == ActionType.Push:
                br = rows[a] + act.agent_row_delta
                bc = cols[a] + act.agent_col_delta
                nbr = br + act.box_row_delta
                nbc = bc + act.box_col_delta
                boxes[nbr][nbc] = boxes[br][bc]
                boxes[br][bc] = ""
                rows[a] += act.agent_row_delta
                cols[a] += act.agent_col_delta

            elif act.type == ActionType.Pull:
                # Pull source is opposite of box movement direction.
                br = rows[a] - act.box_row_delta
                bc = cols[a] - act.box_col_delta
                boxes[rows[a]][cols[a]] = boxes[br][bc]
                boxes[br][bc] = ""
                rows[a] += act.agent_row_delta
                cols[a] += act.agent_col_delta

        child = State(rows, cols, boxes)
        child.parent = self
        child.joint_action = joint_action
        child.g = self.g + 1
        return child

    # ----------------- Conflicts -----------------

    def is_conflicting(self, joint_action: list[Action]) -> bool:
        num_agents = len(joint_action)

        agent_from = [
            (self.agent_rows[i], self.agent_cols[i])
            for i in range(num_agents)
        ]
        agent_to = list(agent_from)
        box_from: list[tuple[int, int] | None] = [None] * num_agents
        box_to: list[tuple[int, int] | None] = [None] * num_agents

        for i, action in enumerate(joint_action):
            ar, ac = agent_from[i]
            if action.type == ActionType.NoOp:
                continue

            agent_to[i] = (ar + action.agent_row_delta, ac + action.agent_col_delta)

            if action.type == ActionType.Push:
                src = (ar + action.agent_row_delta, ac + action.agent_col_delta)
                dst = (src[0] + action.box_row_delta, src[1] + action.box_col_delta)
                box_from[i] = src
                box_to[i] = dst
            elif action.type == ActionType.Pull:
                src = (ar - action.box_row_delta, ac - action.box_col_delta)
                dst = (ar, ac)
                box_from[i] = src
                box_to[i] = dst

        for i in range(num_agents):
            for j in range(i + 1, num_agents):
                if agent_to[i] == agent_to[j]:
                    return True

                if agent_to[i] == agent_from[j] and agent_to[j] == agent_from[i]:
                    return True

                if box_from[i] is not None and box_from[i] == box_from[j]:
                    return True

                if box_to[i] is not None and box_to[i] == box_to[j]:
                    return True

                if box_to[i] is not None and agent_to[j] == box_to[i]:
                    return True

                if box_to[j] is not None and agent_to[i] == box_to[j]:
                    return True

                if box_from[i] is not None and box_to[j] is not None and box_from[i] == box_to[j]:
                    return True

                if box_from[j] is not None and box_to[i] is not None and box_from[j] == box_to[i]:
                    return True

        return False

    # ----------------- Plan extraction -----------------

    def extract_plan(self) -> list[list[Action]]:
        plan: list[list[Action]] = []
        s: State | None = self
        while s is not None and s.joint_action is not None:
            plan.append(s.joint_action)
            s = s.parent
        plan.reverse()
        return plan

    def __hash__(self) -> int:
        if hasattr(self, "_hash"):
            return self._hash  # type: ignore[attr-defined]
        self._hash = hash(
            (
                tuple(self.agent_rows),
                tuple(self.agent_cols),
                tuple(tuple(r) for r in self.boxes),
                tuple(tuple(row) for row in State.goals),
                tuple(tuple(row) for row in State.walls),
            )
        )
        return self._hash

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return False
        return self.agent_rows == other.agent_rows and self.agent_cols == other.agent_cols and self.boxes == other.boxes
