"""Utility to benchmark the search client on a set of levels.

This is not required by the framework, but helps you quickly fill the benchmark tables
in the warmup assignment. It runs the official server.jar with GUI disabled.

Example:
  python run_benchmarks.py --strategy bfs --levels ../levels/MAPF00.lvl ../levels/MAPF01.lvl

Notes:
  - The assignment instructs you to use the values printed on the lines preceding
    "Found solution of length ...". This script extracts those values automatically.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class BenchmarkResult:
    level: str
    strategy: str
    expanded: int | None
    generated: int | None
    time_s: float | None
    solution_len: int | None


STATUS_RE = re.compile(r"#Expanded:\s*([0-9,]+),\s*#Frontier:\s*([0-9,]+),\s*#Generated:\s*([0-9,]+),\s*Time:\s*([0-9.]+)\s*s")
SOL_RE = re.compile(r"Found solution of length\s+(\d+)\.")


def _run_one(level: Path, strategy_flag: str, max_memory_mb: int, timeout_s: int, speed_ms: int) -> BenchmarkResult:
    cmd = [
        "java",
        "-jar",
        "../server.jar",
        "-l",
        str(level),
        "-c",
        f"python -m searchclient.searchclient {strategy_flag} --max-memory {max_memory_mb}",
        "-s",
        str(speed_ms),
        "-t",
        str(timeout_s),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr

    last_status = None
    for m in STATUS_RE.finditer(stderr):
        last_status = m

    expanded = generated = time_s = None
    if last_status:
        expanded = int(last_status.group(1).replace(",", ""))
        generated = int(last_status.group(3).replace(",", ""))
        time_s = float(last_status.group(4))

    sol = SOL_RE.search(stderr)
    sol_len = int(sol.group(1)) if sol else None

    return BenchmarkResult(
        level=level.name,
        strategy=strategy_flag.lstrip("-") if strategy_flag else "bfs",
        expanded=expanded,
        generated=generated,
        time_s=time_s,
        solution_len=sol_len,
    )


def _strategy_to_flag(strategy: str) -> str:
    if strategy == "bfs":
        return "-bfs"
    if strategy == "dfs":
        return "-dfs"
    if strategy == "astar":
        return "-astar"
    if strategy == "greedy":
        return "-greedy"
    raise ValueError("Unknown strategy")


def _print_csv(results: Iterable[BenchmarkResult]) -> None:
    print("Level,Strategy,Expanded,Generated,Time_s,Solution_len")
    for r in results:
        print(
            f"{r.level},{r.strategy},"
            f"{'' if r.expanded is None else r.expanded},"
            f"{'' if r.generated is None else r.generated},"
            f"{'' if r.time_s is None else r.time_s},"
            f"{'' if r.solution_len is None else r.solution_len}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=["bfs", "dfs", "astar", "greedy"], default="bfs")
    ap.add_argument("--max-memory", type=int, default=4096)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--speed", type=int, default=0)
    ap.add_argument("--levels", nargs="+", required=True)
    args = ap.parse_args()

    strategy_flag = _strategy_to_flag(args.strategy)
    results = []
    for lvl in args.levels:
        results.append(
            _run_one(
                level=Path(lvl),
                strategy_flag=strategy_flag,
                max_memory_mb=args.max_memory,
                timeout_s=args.timeout,
                speed_ms=args.speed,
            )
        )

    _print_csv(results)


if __name__ == "__main__":
    main()
