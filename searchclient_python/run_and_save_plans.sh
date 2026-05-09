#!/usr/bin/env bash
set -euo pipefail

LEVELS=(MAPF00 MAPF01 MAPF02 MAPF02C MAPF03 MAPF03C MAPFslidingpuzzle MAPFreorder2)
ALGOS=("bfs" "dfs" "astar" "greedy")

mkdir -p plans logs

for A in "${ALGOS[@]}"; do
  for L in "${LEVELS[@]}"; do
    echo "==== ${A^^} $L ===="

    java -jar ../server.jar \
      -l ../levels/$L.lvl \
      -c "python3 main.py -$A" \
      -t 180 -s 200 \
      2> "logs/${L}_${A}_server.log" | tee "plans/${L}_${A}.plan" > /dev/null || true
  done
done
