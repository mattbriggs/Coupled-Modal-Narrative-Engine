"""Small CLI for opening the sample and running a deterministic scene."""

import argparse
import json

from .project import Project


def main() -> None:
    parser = argparse.ArgumentParser(prog="cmne", description="Local narrative workbench kernel")
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create", help="Create a project; use --sample for Mara and Len")
    create.add_argument("path")
    create.add_argument("--name", default="Untitled scene")
    create.add_argument("--sample", action="store_true")
    run = sub.add_parser("run", help="Replay and realize a project")
    run.add_argument("path")
    run.add_argument("--branch", default="main")
    graph = sub.add_parser("graph", help="Show a lens graph as JSON")
    graph.add_argument("path")
    graph.add_argument("--branch", default="main")
    graph.add_argument("--lens", default="story")
    args = parser.parse_args()
    if args.action == "create":
        result = Project.create(args.path, args.name, args.sample)
        print(result.root)
    elif args.action == "run":
        print(json.dumps(Project(args.path).run(args.branch), indent=2))
    else:
        print(json.dumps(Project(args.path).graph(args.lens, args.branch), indent=2))


if __name__ == "__main__":
    main()
