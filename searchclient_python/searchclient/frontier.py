from abc import ABC, abstractmethod
from collections import deque
import heapq

from .heuristic import Heuristic
from .state import State

class Frontier(ABC):
    @abstractmethod
    def add(self, state: State) -> None: ...

    @abstractmethod
    def pop(self) -> State: ...

    @abstractmethod
    def is_empty(self) -> bool: ...

    @abstractmethod
    def size(self) -> int: ...

    @abstractmethod
    def contains(self, state: State) -> bool: ...

    @abstractmethod
    def get_name(self) -> str: ...


class FrontierBFS(Frontier):
    def __init__(self) -> None:
        super().__init__()
        self.queue: deque[State] = deque()
        self.set: set[State] = set()

    def add(self, state: State) -> None:
        self.queue.append(state)
        self.set.add(state)

    def pop(self) -> State:
        state = self.queue.popleft()
        self.set.remove(state)
        return state

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def size(self) -> int:
        return len(self.queue)

    def contains(self, state: State) -> bool:
        return state in self.set

    def get_name(self) -> str:
        return "breadth-first search"


class FrontierDFS(Frontier):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[State] = []
        self.set: set[State] = set()

    def add(self, state: State) -> None:
        self.stack.append(state)
        self.set.add(state)

    def pop(self) -> State:
        state = self.stack.pop()
        self.set.remove(state)
        return state

    def is_empty(self) -> bool:
        return len(self.stack) == 0

    def size(self) -> int:
        return len(self.stack)

    def contains(self, state: State) -> bool:
        return state in self.set

    def get_name(self) -> str:
        return "depth-first search"


class FrontierBestFirst(Frontier):
    def __init__(self, heuristic: Heuristic) -> None:
        super().__init__()
        self.heuristic = heuristic
        self.heap: list[tuple[float, int, State]] = []
        # Keep only the currently best queued priority per state.
        self.best_priority: dict[State, tuple[float, int]] = {}
        # Monotone tiebreaker so ordering is deterministic when f-values tie.
        self.counter = 0

    def add(self, state: State) -> None:
        priority = self.heuristic.f(state)
        entry = (priority, self.counter)
        prev = self.best_priority.get(state)

        # Keep the best queued entry for each state.
        if prev is None or entry < prev:
            self.best_priority[state] = entry
            heapq.heappush(self.heap, (priority, self.counter, state))

        self.counter += 1

    def pop(self) -> State:
        while self.heap:
            priority, tie, state = heapq.heappop(self.heap)
            best = self.best_priority.get(state)
            if best is not None and best == (priority, tie):
                del self.best_priority[state]
                return state
        raise IndexError("pop from empty best-first frontier")

    def is_empty(self) -> bool:
        return len(self.best_priority) == 0

    def size(self) -> int:
        return len(self.best_priority)

    def contains(self, state: State) -> bool:
        return state in self.best_priority

    def get_name(self) -> str:
        return f"best-first search using {self.heuristic}"
