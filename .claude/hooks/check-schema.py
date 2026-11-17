"""PostToolUse hook for file writes and edits.

If the file written is a JSON file under WF_*/temp/ or WF_*/config/, check it against its definition
in that workflow's config/schema.json (the kind comes from the path and file name, see
common.kind_of). A hook that runs after the call cannot undo it: on a problem it prints the problem on
stderr and exits with code 2, so Claude sees it and fixes the file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared" / "scripts"))


def windows_path(text: str) -> str:
    """Turn a Git Bash path (/c/Users/...) into C:/Users/... on Windows; other paths stay."""
    match = re.match(r"^/([a-zA-Z])(/.*)?$", text)
    if sys.platform.startswith("win") and match:
        return f"{match.group(1).upper()}:{match.group(2) or '/'}"
    return text


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not file_path.lower().endswith(".json"):
        sys.exit(0)
    path = Path(windows_path(file_path))
    if not path.is_absolute():
        path = Path(windows_path(event.get("cwd") or str(ROOT))) / path
    try:
        rel = path.resolve().relative_to(ROOT)
    except ValueError:
        sys.exit(0)
    parts = rel.parts
    if len(parts) < 3 or not parts[0].startswith("WF_") or parts[1] not in ("temp", "config"):
        sys.exit(0)
    try:
        import common
        problems = common.validate(path)
    except Exception as err:  # the check itself failed: tell Claude, do not hide it
        print(f"check-schema.py could not check {rel.as_posix()}: {err}", file=sys.stderr)
        sys.exit(2)
    if problems:
        lines = [f"{rel.as_posix()} does not match {parts[0]}/config/schema.json. Fix the file and save it again:"]
        lines += [f"- {problem}" for problem in problems[:15]]
        if len(problems) > 15:
            lines.append(f"- and {len(problems) - 15} more problems")
        print("\n".join(lines), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
