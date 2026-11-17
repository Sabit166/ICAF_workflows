# ICAF workflows

One repo, several workflows (WF_<name>/). Always open Claude Code in this folder.

## Rules
- Every skill starts by running: python shared/scripts/check-root.py
- Run scripts with python (not python3 or py), with the Bash tool, as one plain command with the
  book name as an argument, for example
  python WF_book_extraction/scripts/crop-blocks.py math_book_pp 7
  No variable in front of the command, and no && or ; in it, or the allow rules will not match.
- Only scripts move or delete files. input/ is read-only, output/ is never replaced or deleted
  (a finished book compiled again gets a new _copy_N folder), and the human commits to git.
  Deny rules and a hook enforce this.
- specs/ holds the build packs: a record only. Do not read them unless asked.
- An agent opens only the paths it is given and writes only the file it is told to write.
- For Bangla text, use the bangla-text skill. Follow .claude/rules/naming.md.
- Everything runs on Claude Haiku 5.5 at medium effort.
- The syntax of Claude Code files depends on the installed version: read the official
  documentation first.
- Python packages: pip install -r requirements.txt

## WF_book_extraction (its agents and skills start with ext-)
- /ext-run-book <book_name> (or: all)    /ext-correct <book_name> <page> <what>
- /ext-compile-book <book_name>           /ext-fix-book <book_name>
- Sample books start with sample_ and live in samples/WF_book_extraction/.

## WF_book_review (its agents and skills start with rev-)
See specs/WF_book_review.md.
