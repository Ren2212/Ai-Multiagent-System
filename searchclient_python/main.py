import argparse
from searchclient.client import SearchClient

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search client")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-bfs", action="store_true")
    group.add_argument("-dfs", action="store_true")
    group.add_argument("-astar", action="store_true")
    group.add_argument("-wastar", nargs="?", type=int, default=False, const=5)
    group.add_argument("-greedy", action="store_true")
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--max-memory", type=float, default=None)
    args = parser.parse_args()

    SearchClient.main(args)
