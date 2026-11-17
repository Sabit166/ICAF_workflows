"""PreToolUse hook for Bash and PowerShell commands.

Blocks (exit code 2, one sentence on stderr) a command that:
- changes anything inside input/ (redirect, cp, mv, rm, tee, Set-Content and the like);
- moves or deletes anything inside WF_*/temp/ or WF_*/output/ (rm, rmdir, del, rd, mv, Remove-Item,
  Move-Item, shutil and the like);
- runs git commit or git push, in any spelling (git -C . push, git --no-pager commit ...).
A part of a command that runs a script from shared/scripts/ or WF_*/scripts/ passes: the scripts do
all the moving and deleting, and guard themselves.
"""
import json
import re
import shlex
import sys

SENTENCE = "Files in input/, temp/ and output/ are moved or deleted only by the scripts."
GIT_SENTENCE = "git commit and git push are blocked: the human commits."

SCRIPT_CALL = re.compile(
    r"""^\s*(?:&\s*)?(?:["']?[\w:\\/.\- ]*?python(?:3(?:\.\d+)?)?(?:\.exe)?["']?|py(?:\.exe)?)\s+
        ["']?(?:\./)?(?:[\w:\\/.\- ]*?[\\/])?(?:shared[\\/]scripts|WF_[\w\-]+[\\/]scripts)[\\/][\w\-]+\.py["']?
        (?:\s|$)""",
    re.IGNORECASE | re.VERBOSE)

PATH_SEP = r"""(?:^|[\s"'=(,;:/\\]|\$)"""
INPUT_PATH = re.compile(PATH_SEP + r"input(?:[\\/]|\s|$|['\"])", re.IGNORECASE)
TEMP_OUTPUT_PATH = re.compile(r"WF_[^\s\\/\"']*[\\/](?:temp|output)(?:[\\/]|\s|$|['\"])", re.IGNORECASE)

WRITE_WORDS = re.compile(
    r"""(?ix)(?:^|[\s;|&(])(?:
        rm|rmdir|del|erase|rd|mv|move|cp|copy|xcopy|robocopy|tee|touch|truncate|dd|install|ln|chmod|chown|
        mkdir|md|ni|new-item|ri|remove-item|mi|move-item|cpi|copy-item|rni|rename-item|ren|rename|
        sc|set-content|ac|add-content|clc|clear-content|out-file|set-itemproperty|
        unlink|sed|perl|awk|python|python3|py|node|powershell|pwsh|cmd)(?=\s|$|\.exe)""")
DELETE_MOVE_WORDS = re.compile(
    r"""(?ix)(?:^|[\s;|&(])(?:
        rm|rmdir|del|erase|rd|mv|move|ri|remove-item|mi|move-item|rni|rename-item|ren|rename|unlink|
        truncate|clc|clear-content|robocopy)(?=\s|$|\.exe)
        |shutil|os\.remove|os\.unlink|os\.rename|os\.replace|os\.rmdir|removedirs|rmtree|\.unlink\(|\.rename\(|
        \.replace\(|\.rmdir\(|\[io\.file\]::(?:delete|move)|\[io\.directory\]::(?:delete|move)|
        find\s.*-delete|-exec\s+rm""")
REDIRECT_TARGET = re.compile(r"(?:^|[^<>&\d-])\d?>>?\s*(?!&)([^\s;|&<>]+)")


def redirects_into_input(part: str) -> bool:
    return any(INPUT_PATH.search(" " + target) for target in REDIRECT_TARGET.findall(part))


def split_parts(command: str) -> list[str]:
    """Split a command line into simple parts at ;, &&, ||, | and new lines."""
    return [p for p in re.split(r"&&|\|\||[;\n|]", command) if p.strip()]


def is_script_call(part: str) -> bool:
    return bool(SCRIPT_CALL.match(part))


def git_blocked(command: str) -> bool:
    for part in split_parts(command):
        try:
            words = shlex.split(part, posix=True)
        except ValueError:
            words = part.split()
        for index, word in enumerate(words):
            if re.fullmatch(r"(?i)(?:.*[\\/])?git(?:\.exe)?", word.strip("&\"'")):
                rest = words[index + 1:]
                skip_next = False
                for item in rest:
                    if skip_next:
                        skip_next = False
                        continue
                    if item in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
                        skip_next = True
                        continue
                    if item.startswith("-"):
                        continue
                    if item.lower() in ("commit", "push"):
                        return True
                    break
        if re.search(r"(?i)\bgit\b[^\n]*\b(commit|push)\b", part) and re.search(r"(?i)(alias|-c\s+alias)", part):
            return True
    return False


def folder_blocked(command: str) -> bool:
    for part in split_parts(command):
        if is_script_call(part):
            continue
        touches_input = bool(INPUT_PATH.search(part))
        touches_kept = bool(TEMP_OUTPUT_PATH.search(part))
        if touches_input and (WRITE_WORDS.search(part) or redirects_into_input(part)):
            return True
        if touches_kept and DELETE_MOVE_WORDS.search(part):
            return True
    return False


def main() -> None:
    try:
        event = json.load(sys.stdin)
        command = (event.get("tool_input") or {}).get("command") or ""
    except Exception:
        print("protect-folders.py could not read the tool call, so the command is blocked.", file=sys.stderr)
        sys.exit(2)
    if not isinstance(command, str) or not command.strip():
        sys.exit(0)
    if git_blocked(command):
        print(GIT_SENTENCE, file=sys.stderr)
        sys.exit(2)
    if folder_blocked(command):
        print(SENTENCE, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
