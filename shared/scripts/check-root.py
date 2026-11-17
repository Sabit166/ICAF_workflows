"""Checks that Claude Code was started at the root of ICAF_workflows.

    python shared/scripts/check-root.py

Prints "ok <root folder>" or the plain sentence below, and stops with an error code.
"""
import sys
from pathlib import Path

NEEDED = ["CLAUDE.md", ".claude/settings.json", "shared", "input"]


def main() -> None:
    here = Path.cwd()
    if all((here / item).exists() for item in NEEDED):
        print(f"ok {here.resolve().as_posix()}")
        return
    print("Open Claude Code at the ICAF_workflows folder, then try again.")
    sys.exit(1)


if __name__ == "__main__":
    main()
