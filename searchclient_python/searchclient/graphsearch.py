from __future__ import annotations

import sys
import time
from typing import Callable

from . import memory
from .action import Action
from .frontier import Frontier
from .state import State

start_time = time.perf_counter()


def search(
    initial_state: State,
    frontier: Frontier,
    goal_test: Callable[[State], bool] | None = None,
    max_expanded: int | None = None,
) -> list[list[Action]] | None:
    if initial_state.has_deadlock():
        print("Initial state contains a static deadlock.", file=sys.stderr, flush=True)
        return None

    output_fixed_solution = False

    if output_fixed_solution:
        # Part 1:
        # The agents will perform the sequence of actions returned by this method.
        # Try to solve a few levels by hand, enter the found solutions below, and run them:

        return [
            [Action.MoveS],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveS],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.MoveE],
            [Action.PushSS],

        ]

    # Part 2:
    # Now try to implement the Graph-Search algorithm from R&N figure 3.7
    # In the case of "failure to find a solution" you should return None.
    # Some useful methods on the state class which you will need to use are:
    # state.is_goal_state() - Returns true if the state is a goal state.
    # state.extract_plan() - Returns the list of actions used to reach this state.
    # state.get_expanded_states() - Returns a list containing the states reachable from the current state.
    # You should also take a look at frontier.py to see which methods the Frontier interface exposes
    #
    # print_search_status(expanded, frontier): As you can see below, the code will print out status
    # (#expanded states, size of the frontier, #generated states, total time used) for every 1000th node
    # generated.
    # You should also make sure to print out these stats when a solution has been found, so you can keep
    # track of the exact total number of states generated!!

    iterations = 0

    frontier.add(initial_state)
    explored: set[State] = set()
    best_g: dict[State, int] = {initial_state: initial_state.g}
    is_goal = goal_test or (lambda s: s.is_goal_state())

    while True:
        iterations += 1
        if iterations % 1000 == 0:
            print_search_status(explored, frontier)

        if memory.get_usage() > memory.max_usage:
            print_search_status(explored, frontier)
            print("Maximum memory usage exceeded.", file=sys.stderr, flush=True)
            return None

        # Your code here...
        if frontier.is_empty():
            return None

        state = frontier.pop()

        # Ignore stale frontier entries when a cheaper path to the same state
        # has already been generated.
        known_g = best_g.get(state)
        if known_g is None or state.g != known_g:
            continue

        if is_goal(state):
            print_search_status(explored, frontier)
            return state.extract_plan()

        explored.add(state)

        if max_expanded is not None and len(explored) >= max_expanded:
            return None

        for neighbor in state.get_expanded_states():
            if neighbor in explored:
                continue

            old_g = best_g.get(neighbor)
            if old_g is None or neighbor.g < old_g:
                best_g[neighbor] = neighbor.g
                frontier.add(neighbor)


def print_search_status(explored: set[State], frontier: Frontier) -> None:
    elapsed_time = time.perf_counter() - start_time
    print(
        f"#Expanded: {len(explored):8,}, #Frontier: {frontier.size():8,}, "
        f"#Generated: {len(explored) + frontier.size():8,}, Time: {elapsed_time:3.3f} s\n"
        f"[Alloc: {memory.get_usage():4.2f} MB, MaxAlloc: {memory.max_usage:4.2f} MB]",
        file=sys.stderr,
        flush=True,
    )
