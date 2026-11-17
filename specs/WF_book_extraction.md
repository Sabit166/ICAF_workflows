# WF_book_extraction: Build Pack for Claude (specs/WF_book_extraction.md)

This file is the build pack for the workflow WF_book_extraction in the repo ICAF_workflows. It says what each file must contain, and Claude Code builds the files from it. The parts marked Shared are used by every workflow. After the build, the built files are the rules, and this pack is only a record: it lives at specs/WF_book_extraction.md and is never imported from any CLAUDE.md, so it costs no tokens at run time. It has no steps for humans. A separate human guide holds those. If the two disagree, this file wins.

## Version rule (Shared)

Claude Code changes between versions: file formats, setting names, command-line options and limits. This pack therefore says what each file must achieve, and its examples are illustrative.

- Before creating any file under .claude/, Claude Code reads the official Claude Code documentation for the installed version (or asks its built-in claude-code-guide agent) and writes the syntax that version documents. The pages that matter are: subagents, skills, hooks, settings and permissions, and memory (CLAUDE.md and rules).
- The facts below were checked against the official documentation in November 2026. Confirm each one for the installed version.
  - Where things load from. settings.json (permissions, hooks and the other keys) is read only from the .claude/ folder of the folder where Claude Code starts, with no parent fallback. CLAUDE.md and .claude/rules/ load from the start folder and every folder above it. Skills and agents are found in the start folder and every folder above it, up to the git root. So Claude Code is always started at ICAF_workflows/.
  - Agents. A file needs name and description. tools, model, effort and omitClaudeMd are optional, and so is skills, which preloads whole skills into the agent. A field the version does not know is ignored without an error.
  - Skills. A skill is a folder with a SKILL.md. Its header has name, description and argument-hint. The text typed after the slash command reaches the skill as its argument. A skill can be set so that only the human starts it.
  - Hooks. A hook receives the tool call as JSON on its standard input. Exit code 2 blocks a call before it runs, even when an allow rule would permit it. After the call has run, a hook can only report to Claude.
  - Permission rules. For files, only Edit(path) and Read(path) rules are matched. Edit covers every file-writing tool, and a Write(path) rule never matches. A /path pattern in the project's settings.json is anchored at the folder where Claude Code starts. Deny rules do not cover what a script does inside itself.
  - Shell allow rules. An allow rule does not match a command that starts with a variable assignment (NAME=value python ...), and a command joined with && or ; must match as separate parts. So every script gets the book as an argument, and every command is one plain command.
  - Trust. Allow rules in the project's settings.json apply only after the human accepts the workspace trust dialog for the repo.
  - Size and context. CLAUDE.md should stay under about 200 lines. Subagents load CLAUDE.md too, unless their agent file says not to.
  - Subagents. They can start subagents in newer versions, to a depth limit. Do not rely on it: all parallel work is started by the main session. The default limit is 20 subagents at the same time (changeable). If it is lower than max_parallel, run as many as it allows and queue the rest. A wave ends when every run of its step has reported back. Background subagents show their permission questions in the main session, so allow what they need in settings.json first.
  - Many workflows. Every session loads the short description of every agent and skill of every workflow. Keep each description to one short line. When there are more than about 5 workflows, turn each workflow into a plugin and enable only the one in use.
- If the installed version differs from any fact above, follow the documentation, and write the difference in a short note at the top of CLAUDE.local.md.

## One repo, one root (Shared)

- One git repo, ICAF_workflows. Claude Code is always started in its root folder. One .claude/, one CLAUDE.md and one settings.json serve all workflows.
- A workflow is a folder WF_<name>/ with its own config/, scripts/, temp/ and output/. It has no .claude/ of its own.
- What workflows share has one home at the root: input/ (the books), samples/, specs/ and shared/.
- Every agent and skill name starts with its workflow's prefix: ext- for WF_book_extraction, rev- for WF_book_review. A name never hints at the wrong workflow.
- In this pack, <wf> means WF_book_extraction. A path that starts with input/, shared/, samples/, specs/ or .claude/ is at the root. A path that starts with <wf>/ is inside the workflow.

## Goal

Read the PDF books in input/, one book at a time and page by page. For every page save:

- every word exactly as printed (verbatim, nothing fixed), with its box, type, font, size, bold, italic, colour, alignment and reading order;
- every image block (see Image blocks) as a cropped image file plus a detailed written description, a short summary, a purpose and rebuild notes;
- the page background, as a detailed description and a short summary;
- the page context: plain facts about the page, links between its blocks and a summary of its layout. Never what the page means.

Then check the saved data against the page. A finished book is one merged JSON with all the detail, one .md and one .docx (full text with its styles, the full context, and short image and background descriptions), all named after the PDF, plus the crops, the renders and the log.

Limits: text can be exact. An image block is saved as a crop and written descriptions, and the original PDF stays the exact source of the pictures. A Claude reading and the PDF's own text can be wrong in the same way, and two Claude readings can make the same mistake, so agreement is strong evidence, not proof.

## Image blocks

An image block is a picture, an image, or any graphic object. These are its kinds (the kind field uses exactly these snake_case words): picture, photo, drawing, diagram, chart, graph, table, map, timeline, infographic, maths_model (such as a number line or counting blocks), model, parse_tree, concept_map, screenshot, icon, shape, other.

- Each image block gets a crop saved in images/ (see crop-images.py) and descriptions in the page JSON.
- Words inside an image block are still text. Table cells, chart labels, diagram labels, numbers on a number line and words in a screenshot are listed by the layout-vision agent as text blocks, and they are read, voted and saved like any other text. The image block adds the crop and the descriptions. Its descriptions do not repeat those words.
- The page background (colour, pattern, a border around the page) is not an image block. It is described in background and gets no crop.

## Parts

| Part | File | Job |
|---|---|---|
| Shared: root rules | CLAUDE.md, .claude/rules/naming.md, .claude/skills/bangla-text/SKILL.md | Shared rules, naming rules, and the Bangla text rules as a reference skill that the agents preload |
| Shared: settings and hooks | .claude/settings.json, .claude/hooks/ | Permissions and two hooks: protect-folders.py, check-schema.py |
| Shared: scripts | shared/scripts/ | common.py (paths, log, checks) and check-root.py |
| Shared: reference | shared/reference/ | bangla-words.txt |
| Skill ext-run-book | .claude/skills/ext-run-book/SKILL.md | /ext-run-book <book_name>: runs the pipeline for one book, page by page, in waves. Holds the main-session rules |
| Skill ext-compile-book | .claude/skills/ext-compile-book/SKILL.md | /ext-compile-book <book_name>: merges the pages, builds the .md and the .docx, moves the book to output/. A finished book compiled again goes to a new _copy_N folder; nothing is replaced |
| Skill ext-fix-book | .claude/skills/ext-fix-book/SKILL.md | /ext-fix-book <book_name>: reopens a compiled book so a mistake can be fixed. Skill ext-correct (.claude/skills/ext-correct/SKILL.md): /ext-correct <book_name> <page> <what> fixes a word or a crop, or runs a page again |
| Agent ext-text-reader | .claude/agents/ext-text-reader.md | Blind reading of text block crops. Claude vision does the reading. Google OCR is optional and off |
| Agent ext-layout-vision | .claude/agents/ext-layout-vision.md | Text blocks, boxes, styles, reading order. Never writes words |
| Agent ext-image-bg | .claude/agents/ext-image-bg.md | Finds every image block and the background and writes their descriptions |
| Agent ext-context | .claude/agents/ext-context.md | Page facts, links between blocks and a layout summary. No meaning |
| Agent ext-verifier | .claude/agents/ext-verifier.md | Compares the page JSON and the crops with the page render and replies with a report. Read-only |
| Workflow scripts | <wf>/scripts/ | Everything deterministic in this workflow. Listed in Scripts |
| Workflow config | <wf>/config/ | schema.json, render.json, run.json, ocr.json |

## Model and effort

The main session and every agent run on Claude Haiku 5.5 at medium effort. An agent file names the model (the id claude-haiku-5-5, or the alias your version accepts) and, if the version knows the field, effort: medium. The main session's own model and effort come from its menu or settings. Confirm in the documentation, and with the tools that show the running model, which model really runs.

## Reading mode

Claude only: there is no Google key. ocr-page.py is optional and skipped (<wf>/config/ocr.json has enabled: false). If a key is added later, run ocr-page.py before the layout-vision agent, and vote-text.py then uses ocr.json as one more reader.

## Statuses and scores

- Page status is one of: new, extracted, redo, done. It lives only in log.csv.
- text_status of a text block is one of: agreed, voted, unsure. unsure means all readers disagreed. The text keeps the best guess with [?] in front.
- Scores are checked against <wf>/config/run.json. For each of confidence (0–100, from the verifier), coverage (0–1, from check-page.py) and text agreement (0–1, from vote-text.py) there is a good and a low limit. At or above good: good. At or above low but below good: middle. Below low: low.
- All three good: the page is done with no note. Any middle: done, with a check note. Any low: the page is run again once, then the better try is kept, and the page is done with a check note. A block marked unsure, any unknown words, or any doubts also get a check note.
- Two tags need a human before the book can be compiled. latin_text (set by check-page.py: a Bengali block that is still mostly Latin letters) counts as a low score, so the page is run again once; if it is still there after the second try, finish-page.py adds needs_human. needs_human is also set by vote-text.py when a symbol is left inside a Bengali word after conversion. A page tagged needs_human is still done, so a run never loops on it. But /ext-compile-book refuses the book until the human fixes the page with /ext-correct, which removes the tag.
- The limits are starting guesses. Tune them after the sample test. No run ever stops to wait for a human: a page tagged needs_human is done, and the tag only blocks compiling.

## Folder map

```
ICAF_workflows/                      one git repo. Open Claude Code here, always
├── CLAUDE.md                        only what Claude can't find by reading the repo (under 200 lines, no folder layout)
├── CLAUDE.local.md                  personal notes, not shared (git ignores it)
├── .gitignore                       CLAUDE.local.md, .claude/settings.local.json, input/, WF_*/temp/, __pycache__/
│
├── .claude/                         the only .claude folder: settings are read from here only
│   ├── settings.json                permissions and hooks for all workflows
│   ├── settings.local.json          personal, not shared (git ignores it)
│   ├── hooks/
│   │   ├── protect-folders.py       blocks Claude's own commands that change input/, or move or delete files in WF_*/temp/ or WF_*/output/
│   │   └── check-schema.py          checks a saved JSON file against its workflow's config/schema.json
│   ├── agents/
│   │   ├── ext-text-reader.md
│   │   ├── ext-layout-vision.md
│   │   ├── ext-image-bg.md
│   │   ├── ext-context.md
│   │   └── ext-verifier.md          (rev-*.md files come with the review workflow)
│   ├── skills/
│   │   ├── ext-run-book/SKILL.md
│   │   ├── ext-compile-book/SKILL.md
│   │   ├── ext-fix-book/SKILL.md
│   │   ├── ext-correct/SKILL.md     (rev-*/ folders come with the review workflow)
│   │   └── bangla-text/SKILL.md     shared reference skill: the Bangla text rules, preloaded by the agents that read text
│   └── rules/
│       └── naming.md
│
├── input/                           all book PDFs, read-only, any number. Git ignores it
│   └── <book>.pdf                   one file per book, for example Math-Book-PP.pdf
├── samples/                         git tracks it
│   ├── WF_book_extraction/
│   │   ├── input/sample_book.pdf    a short sample PDF. A sample's book name always starts with sample_
│   │   └── output/sample_book/      its checked result: the correct answer for tests
│   │       ├── sample_book.json, sample_book.md, sample_book.docx, log.csv
│   │       ├── renders/page_001.jpg ...
│   │       └── images/page_001_i1.jpg ...
│   └── WF_book_review/{input,output}/    filled when that workflow is built
├── specs/
│   ├── WF_book_extraction.md        this pack, a record only
│   └── WF_book_review.md            the build pack of the review workflow (its own document)
├── shared/
│   ├── scripts/
│   │   ├── common.py
│   │   └── check-root.py
│   └── reference/
│       └── bangla-words.txt
│
├── WF_book_extraction/
│   ├── config/
│   │   ├── schema.json
│   │   ├── render.json
│   │   ├── run.json
│   │   └── ocr.json
│   ├── scripts/
│   │   ├── cut-pages.py
│   │   ├── check-text-layer.py
│   │   ├── ocr-page.py              optional
│   │   ├── crop-blocks.py
│   │   ├── vote-text.py
│   │   ├── crop-images.py
│   │   ├── merge-page.py
│   │   ├── check-page.py
│   │   ├── swap-try.py
│   │   ├── finish-page.py
│   │   ├── build-review.py
│   │   ├── merge-book.py
│   │   ├── make-md.py
│   │   ├── make-docx.py
│   │   ├── finalize-book.py
│   │   └── reopen-book.py
│   ├── temp/<book_name>/            git ignores it. Nothing in it is deleted until the book is final. A sample book works here too
│   │   ├── <book_name>_review.docx  the ONE file the human checks (rebuilt after every batch). TEMPORARY
│   │   ├── book-info.json           size and scale of every page render, and the PDF's fingerprint. TEMPORARY
│   │   ├── pdf-words.json           the PDF's own words for every page. TEMPORARY
│   │   ├── pages/
│   │   │   └── page-001.json ...    one JSON per page. TEMPORARY
│   │   ├── work/
│   │   │   └── page-001/ ...        one folder per page. TEMPORARY
│   │   │       ├── layout.json
│   │   │       ├── images.json
│   │   │       ├── context.json
│   │   │       ├── blocks/t1.png, t2.png ...
│   │   │       ├── text-a.json
│   │   │       ├── text-b.json
│   │   │       ├── text-c.json
│   │   │       ├── text-final.json
│   │   │       ├── second-read.txt
│   │   │       ├── third-read.txt
│   │   │       ├── votes.json
│   │   │       ├── leftovers.json
│   │   │       ├── report.md
│   │   │       ├── ocr.json         only when Google OCR is on
│   │   │       └── try1/            only when a page is redone: the first try's files and scores-json
│   │   ├── <book_name>.json, <book_name>.md, <book_name>.docx   built by the compile skill, then copied to output
│   │   ├── renders/page_001.jpg ... KEPT: one .jpg per page, copied to output at the end
│   │   ├── images/page_001_i1.jpg ... KEPT: crops of the image blocks, copied to output at the end
│   │   ├── log.csv                  KEPT: copied to output at the end
│   │   └── log.csv.lock             exists only for a moment while a script updates the log
│   └── output/                      git tracks it. Never holds a sample book. Nothing in it is ever replaced or deleted
│       ├── <book_name>/             the finished book
│       │   ├── <book_name>.json     all pages merged, with all the detail
│       │   ├── <book_name>.md
│       │   ├── <book_name>.docx
│       │   ├── log.csv
│       │   ├── renders/page_001.jpg ...   one .jpg per page
│       │   └── images/page_001_i1.jpg ... crops of the image blocks (.png for line art)
│       └── <book_name>_copy_1/ ...   only when a finished book is compiled again: a new copy, with <book_name>_copy_1.json, .md and .docx inside
│
└── WF_book_review/                  same template (config/, scripts/, temp/, output/), built from specs/WF_book_review.md
```

The naming split: files that end up in an output/ folder (renders, crops, the final files and the log) are snake_case from the start. Every other file that Claude builds is kebab-case. The rules are in Naming rules.

What is kept and what is temporary

- input/ is read-only. Nothing is ever written there. Git ignores it.
- Kept (the finished book): <book_name>.json, <book_name>.md, <book_name>.docx, log.csv, renders/ (one .jpg per page) and images/ (the crops of the image blocks). finalize-book.py copies them to <wf>/output/<book_name>/, and git tracks them.
- Temporary (everything else in temp/<book_name>/): the review file, book-info.json, pdf-words.json, pages/, work/ (the text block crops, readings, votes, reports and the rest) and log.csv.lock.
- Only scripts move or delete files. Nothing in temp/ is deleted during a run. common.py clear-work empties one page's work folder (except try1/) when that page starts again, swap-try.py saves and restores a try, and finalize-book.py deletes the book's temp folder at the end. Claude's own move and delete commands in input/, temp/ and output/ are blocked by a hook.
- The end of a book is crash-safe. finalize-book.py copies the kept files to output/, checks them, and only then deletes the temp folder. A crash never leaves the book split between temp/ and output/.
- <wf>/output/ is written only by finalize-book.py, and nothing in it is ever replaced or deleted. If output/<book_name>/ already exists, a new result goes to output/<book_name>_copy_1/, then _copy_2, and so on.
- Sample books (book name starts with sample_) never go to <wf>/output/. The first compile saves the result in samples/<wf>/output/<book_name>/, and later compiles compare with it (see finalize-book.py).
- Git: only input/, WF_*/temp/ and the personal files are ignored. Finished books (with all their copies), samples, specs and all project files are tracked. The human commits (for example with the VS Code Source Control panel). git commit and git push are blocked for Claude.

## How a book moves

- The PDF goes into input/.
- /ext-run-book <book_name> creates <wf>/temp/<book_name>/ and works page by page, in batches, with many pages at the same time. It rebuilds the review file after every batch. The human reads that file and sends corrections.
- /ext-compile-book <book_name> merges the page JSON files into <book_name>.json, builds <book_name>.md and <book_name>.docx from it, and copies the finished files to <wf>/output/<book_name>/.
- A mistake found later: /ext-fix-book <book_name> reopens the newest version into <wf>/temp/<book_name>/. After the corrections, /ext-compile-book <book_name> saves the result as a new copy, <wf>/output/<book_name>_copy_N/. Nothing is replaced.

## Several books

- One folder per book: each book has <wf>/temp/<book_name>/ and later <wf>/output/<book_name>/. The book name comes from the PDF's file name (see Naming rules). Books never share a folder or a log.
- Choosing the book: /ext-run-book <book_name> names the book, or says all. Every script that works on a book gets the book name as its first argument and finds the PDF in input/ itself. A script never guesses between books.
- Two PDFs with the same book name are a conflict. For example, Math Book.pdf and math-book.pdf both give math_book. Stop and ask the human to rename one.
- A finished book is not run again. If <wf>/output/<book_name>/ exists, /ext-run-book stops and says so. To correct a finished book, use /ext-fix-book.
- One book at a time: the main session finishes one book's pages before starting the next. Pages of two books never run at the same time.
- Each book has its own review file and log.

## Naming rules (Shared)

This section is the content of .claude/rules/naming.md. Follow it for every file, folder, script, JSON key and column.

- Output-bound files are snake_case: every file that ends up in an output/ folder, from the moment it is made. These are the renders (page_001.jpg), the crops (page_001_i1.jpg), <book_name>.json, <book_name>.md, <book_name>.docx and log.csv.
- Every other file Claude builds is kebab-case (lowercase words joined by hyphens): scripts (cut-pages.py), hooks, agent files (ext-text-reader.md), skill folders (ext-run-book/), rule files, reference files (bangla-words.txt), and the working files in temp/ (book-info.json, pdf-words.json, pages/page-001.json, work/page-001/, text-a.json, second-read.txt).
- Prefixes: every agent and skill name starts with its workflow's prefix (ext-, rev-). There is no unprefixed agent or skill.
- Names the human chose stay as they are: ICAF_workflows, the workflow folders (WF_book_extraction), specs/WF_book_extraction.md, <book_name>_review.docx, and the sample_ start of a sample book's name. Tool names stay as they are: CLAUDE.md, CLAUDE.local.md, SKILL.md, .claude/, settings.json, settings.local.json, .gitignore, log.csv.lock. common.py is one word and is imported by the other scripts, so it has no hyphen. A script whose name has a hyphen can be run but not imported.
- Data is always snake_case: JSON keys, CSV columns and fixed values (text_status, maths_model, unsure), even inside kebab-case files.
- Python code: variables and functions in snake_case, classes in PascalCase, constants in UPPER_SNAKE_CASE (PEP 8).
- Page numbers have at least 3 digits. Output-bound names use page_001, and internal names use page-001. In this file, XXX stands for the page number.
- Placeholders are written in angle brackets, in snake_case: <book_name>, <wf>.
- Book name: the PDF's file name without .pdf, changed to snake_case: lowercase English letters, spaces and hyphens become _, Bangla letters stay, and any other character a file name cannot hold becomes _. Example: Math-Book-PP.pdf gives math_book_pp.

## Bangla text rules (Shared)

This section is the content of .claude/skills/bangla-text/SKILL.md, a reference skill shared by every workflow. Its header has name: bangla-text, a one-line description ("The Bangla text rules: verbatim, Unicode NFC, Bijoy text. Use when reading, comparing or checking Bangla text.") and user-invocable: false, so it is not in the slash-command list. Claude loads it when Bangla text is involved, and the agents ext-text-reader and ext-verifier preload it with skills: [bangla-text], because they do not load CLAUDE.md. This is the only copy of these rules.

- Verbatim. Save the letters exactly as printed. Never fix spelling, never guess missing letters, never make a sentence sensible. Write [?] where a part is unreadable or unsure.
- Unicode. Save and compare text in Unicode NFC. When comparing, use one kind of space, quote mark and dash. Never change letters.
- Bijoy and ANSI text. The PDF's hidden text is often in old-style fonts (Bijoy, SutonnyMJ) and looks like nonsense. It is stored in visual order, so it fails any Unicode check. Convert it to Unicode first, and only with bijoy_to_unicode() in common.py (one conversion table). Never change letters by hand or by guess. Never discard converted text: if it still looks wrong, keep it in the vote and flag it.
- Converter crashes. Add a trailing space to the word before converting it and remove it afterwards. If the converter still fails on a word, keep the word as it is and go on. Never stop the run.
- The PDF's own text is a reader, never the only one. A disagreement with it always triggers another Claude reading. Latin letters (Pc, Rj, NU and the like) inside Bengali text are Bijoy code, not English: the vote script converts them, never an agent. A symbol such as ' or another ASCII sign left inside a Bengali word after conversion is a doubt, and a human fixes it.
- Word list. shared/reference/bangla-words.txt is only a hint. Names and rare forms show up as unknown even when they are correct.
- Most common mistakes: joined letters (যুক্তবর্ণ like ক্ষ, ন্ত) and vowel signs (ি, ু, ঁ). Look at these first.

## Project files

These sections give the content of the project's own files. Claude Code creates each file from them, following the Version rule.

### CLAUDE.md at the root (Shared, under 200 lines)

```
# ICAF workflows

One repo, several workflows (WF_<name>/). Always open Claude Code in this folder.

## Rules
- Every skill starts by running: python shared/scripts/check-root.py
- Run scripts with python (not python3 or py), as one plain command with the book name as an
  argument, for example
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

## WF_book_extraction (its agents and skills start with ext-)
- /ext-run-book <book_name> (or: all)    /ext-correct <book_name> <page> <what>
- /ext-compile-book <book_name>           /ext-fix-book <book_name>
- Sample books start with sample_ and live in samples/WF_book_extraction/.

## WF_book_review (its agents and skills start with rev-)
See specs/WF_book_review.md.
```

### .gitignore (Shared)

```
CLAUDE.local.md
.claude/settings.local.json
input/
WF_*/temp/
__pycache__/
```

### CLAUDE.local.md and .claude/settings.local.json (Shared)

Personal and not shared (git ignores both). CLAUDE.local.md starts as one line, # Personal notes. settings.local.json starts as {}.

### .claude/settings.json (Shared)

What it must achieve:

- Allow, without asking: reading files; editing files inside any workflow's temp/ (this covers every agent, so a run of 20 does not stop to ask); running the scripts as plain commands.
- Deny Claude's own file tools on input/, on every workflow's output/ and on every workflow's config/schema.json. Only finalize-book.py writes output/.
- Deny git commit and git push: the human commits. The protect-folders.py hook also blocks other spellings of them.
- Register the two hooks: protect-folders.py before every shell command, and check-schema.py after every file write or edit. Give protect-folders.py onFailure: "block" (if the version knows it), so that a crash of the hook itself still blocks the command.

An example. It is illustrative: write the form your version documents, and use Edit(...) for file paths. The human must accept the workspace trust dialog once, or the allow rules do not apply.

```
{
  "permissions": {
    "allow": ["Read", "Edit(/WF_*/temp/**)", "Bash(python shared/scripts/*)", "Bash(python WF_book_extraction/scripts/*)"],
    "deny": ["Edit(/input/**)", "Edit(/WF_*/output/**)", "Edit(/WF_*/config/schema.json)", "Bash(git commit *)", "Bash(git push *)"]
  },
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect-folders.py\""}]}
    ],
    "PostToolUse": [
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/check-schema.py\""}]}
    ]
  }
}
```

The form of the hook commands depends on the shell of the computer (PowerShell and bash write the project folder variable differently). Check the hooks guide for the installed version.

### Hooks (Shared)

Both are Python scripts in .claude/hooks/. A hook reads the tool call as JSON on its standard input (tool_name, and under tool_input the command for a shell call or the file_path for a file tool). To block a call, a before-the-call hook prints one plain sentence on its error output and exits with code 2. Permission rules do not see what a script does inside, so the hooks cover only Claude's own commands. The scripts in shared/scripts/ and WF_*/scripts/ guard themselves. Each hook finds the repo root itself, from the hook script's own folder.

- protect-folders.py (before a shell command). Block the command if it changes anything inside input/ (a redirect, cp, mv, rm, tee and the like), or moves or deletes anything inside WF_*/temp/ or WF_*/output/ (rm, rmdir, del, rd, mv, Remove-Item, Move-Item, shutil and the like). A command that runs a script from shared/scripts/ or WF_*/scripts/ passes: the scripts do all moving and deleting. It also blocks git commit and git push in any spelling (such as git -C . push): the human commits. The sentence: "Files in input/, temp/ and output/ are moved or deleted only by the scripts."
- check-schema.py (after a file write or edit). If the file written is a JSON file under WF_*/temp/ or WF_*/config/, check it against its definition in that workflow's config/schema.json (the kind comes from the path and file name). A hook that runs after the call cannot undo it. It prints the problem on its error output and exits with code 2, so that Claude sees the problem and fixes the file.

### shared/reference/ and samples/ (Shared)

- shared/reference/bangla-words.txt: a word list downloaded from an open source. Tell the human which list was used and its licence before saving it. It is only a hint.
- samples/WF_book_extraction/input/ holds a short PDF (6 pages: text-heavy, picture-heavy, a table, a cover, a page with no text, and a page in a Bijoy font that the PDF does not embed, so its Bengali renders as Latin letters such as Pc, Rj). Its book name starts with sample_, for example sample_book.pdf. It is run straight from there: it is never copied into input/, and its result never goes to WF_book_extraction/output/. The first compile saves the result in samples/WF_book_extraction/output/<book_name>/, which the human checks by hand and commits. Every later compile compares the new result with it and lists the differences (see finalize-book.py). Run the sample after any change to the workflow.

### <wf>/config/

<wf>/config/schema.json is built from File shapes below: one definition for each kind of file (page, book, book_info, pdf_words, layout, images, context, reader_answer for text-a, text-b, text-c and text-final, votes, leftovers, ocr). The others hold the numbers that were in the prose. Scripts and skills read them, so a number is changed in one place.

<wf>/config/render.json

```
{
  "page_render": {"long_side_px": 1600, "min_long_side_px": 1400, "jpeg_quality": 85, "min_jpeg_quality": 60, "max_kb": 500},
  "block_crop": {"dpi": 300, "padding_px": 10},
  "image_crop": {"dpi": 200, "padding_px": 5, "jpeg_quality": 90, "min_jpeg_quality": 70, "min_long_side_px": 1200, "max_kb": 1024,
                 "jpeg_kinds": ["picture", "photo", "drawing", "icon", "shape", "other"]}
}
```

<wf>/config/run.json

```
{
  "batch_size": 20,
  "max_parallel": 20,
  "pilot_pages": 5,
  "tries": 2,
  "scores": {
    "confidence": {"good": 95, "low": 90},
    "coverage": {"good": 0.98, "low": 0.95},
    "text_agreement": {"good": 0.99, "low": 0.97}
  },
  "stop_after_same_note": 3,
  "spot_check": {"first_pages": 50, "every_in_first": 5, "every_after": 20},
  "log_lock": {"wait_s": 30, "stale_s": 60},
  "rate_limit": {"wait_s": 30, "max_wait_s": 300, "max_retries": 3}
}
```

<wf>/config/ocr.json

```
{"enabled": false, "engine": "google_vision", "language_hints": ["bn", "en"], "dpi": 300}
```

## File shapes

<wf>/config/schema.json must describe every file below, one definition per kind of file. All keys use snake_case, in every file. Positions are in pixels from the top-left corner of the page render (<wf>/temp/<book_name>/renders/page_XXX.jpg), and box is always [left, top, right, bottom]. In this section a path that starts with temp/ is inside <wf>/.

### Page JSON

One file per page: temp/<book_name>/pages/page-XXX.json.

```
{
  "page": 1,
  "size": {"width": 1131, "height": 1600},
  "background": {
    "color": "#FFF8E7",
    "summary": "Cream page with a green leaf border all around the edge.",
    "description": "Light cream page with a green leaf border running all around the edge. The leaves are simple flat shapes in two greens, all pointing clockwise, with small gaps between them.",
    "rebuild_notes": "Border is about 28 px wide, leaf shapes repeat every 90 px, leaf colours #4A7C3A and #7FB069",
    "boxes": [[0, 0, 1131, 28], [0, 1572, 1131, 1600], [0, 0, 28, 1600], [1103, 0, 1131, 1600]]
  },
  "text_blocks": [
    {
      "id": "t1",
      "type": "heading",
      "lang": "bn",
      "text": "অ – অজগর",
      "text_status": "agreed",
      "box": [90, 70, 550, 150],
      "font": {"name": "SolaimanLipi", "size_pt": 36, "bold": true, "italic": false, "color": "#C0392B"},
      "align": "left",
      "order": 1,
      "read_agreement": 1.0,
      "other_readings": []
    }
  ],
  "images": [
    {
      "id": "i1",
      "file": "images/page_001_i1.jpg",
      "box": [600, 70, 1040, 420],
      "kind": "drawing",
      "summary": "A smiling green cartoon snake curled into a circle, at the top right.",
      "description": "A smiling green cartoon snake curled into a loose circle. The head sits at the top right of the circle and faces left. The body has three lighter green stripes. One white round eye with a black dot. A thin red tongue sticks out of the mouth.",
      "purpose": "Shows the word for the letter অ",
      "style": "flat cartoon, thick dark outline, no shadow",
      "main_colors": ["#4CAF50", "#1B5E20", "#FFFFFF"],
      "layer": 2,
      "rotation_deg": 0,
      "opacity": 1.0,
      "overlaps_text": [],
      "rebuild_notes": "Outline about 4 px; head is about one quarter of the circle width; stripes run across the body, not along it"
    }
  ],
  "context": {
    "page_type": "lesson",
    "printed_page_number": "12",
    "heading_ids": ["t1"],
    "running_header_ids": [],
    "running_footer_ids": [],
    "reading_flow": ["t1", "i1"],
    "links": [{"from": "t1", "to": "i1", "relation": "label_of"}],
    "languages": ["bn"],
    "layout_summary": "One column. A heading at the top left and a large drawing at the top right. No header or footer."
  },
  "unknown_words": [],
  "doubts": ["t3: second word unclear, text-a and text-b disagree"],
  "review": {
    "confidence": 95,
    "coverage": 0.99,
    "text_agreement": 0.99,
    "tries": 1,
    "leftover_spots": [],
    "checker_notes": "No mistakes found."
  }
}
```

Rules:

- text comes from the vote (votes.json). No single reader may write it. Only a human may change it afterwards, with /ext-correct, which edits the page JSON.
- type of a text block is one of: heading, body, caption, label, table_text, other.
- other_readings holds the readings that lost, for blocks marked voted or unsure: a list of {"reader": "text_a" | "text_b" | "text_c" | "pdf" | "ocr", "text": "..."}. It is empty for agreed blocks.
- Every image block has a file (its crop in images/, .jpg or .png), a kind (one of the kinds in Image blocks), a summary (one or two plain sentences), a detailed description (several sentences), a purpose and rebuild_notes. The crop and the description together must be good enough for an artist to redraw the picture or rebuild the table, chart or model. For a chart, graph, table, map, timeline, infographic, maths model, parse tree or concept map, the description must give its structure and the data it shows (axes, groups, values, trends, nodes and links, positions), because the words inside are text blocks but their layout is not.
- The background has a summary and a detailed description in the same way, and boxes: the areas of the page where the background has ink, such as border strips or a pattern. check-page.py paints these out. A plain page has an empty boxes list.
- context holds facts only, never meaning. page_type is one of: cover, contents, lesson, exercise, answer_key, index, blank, other. relation is one of: caption_of, label_of, continues, answer_to, part_of. Every id it uses must exist in text_blocks or images. layout_summary is one to three plain sentences.
- review is added by finish-page.py when the page is done, so the schema makes it optional. tries is 1, or 2 after a redo.
- A page that could not be processed has no page JSON. In the Book JSON it appears in the short form {"page": 7, "failed": true, "note": "This page could not be processed."}. The schema allows this short form only inside the Book JSON.
- The status of a page is only in log.csv, never in the page JSON.
- The purpose and rebuild_notes fields are for image blocks only. Text blocks get no purpose and no meaning.

### Book JSON

<book_name>.json holds all pages in order, with all their detail: {"book": "math_book_pp", "source_pdf": "Math-Book-PP.pdf", "page_count": 120, "pages": [ ...the page JSON objects... ]}.

### Book files

Both are in temp/<book_name>/.

| File | Made by | Shape |
|---|---|---|
| book-info.json | cut-pages.py | {"pages": {"page_001": {"width": 1131, "height": 1600, "scale": 1.9, "file_size_kb": 412}}, "pdf_sha256": "<the PDF's fingerprint>"} |
| pdf-words.json | check-text-layer.py | {"pages": {"page_001": {"words": [{"text": "আমার", "box": [l, t, r, b]}], "bijoy": true, "doubt": false}}}. A page without a usable text layer has no entry |

### Page working files

All of these are in temp/<book_name>/work/page-XXX/.

| File | Made by | Shape |
|---|---|---|
| layout.json | ext-layout-vision | {"size": {"width": 1131, "height": 1600}, "text_blocks": [{"id", "type", "lang", "box", "font", "align", "order"}], "doubts": []} |
| images.json | ext-image-bg | {"background": {...}, "images": [{"id", "box", "kind", "summary", "description", "purpose", "style", "main_colors", "layer", "rotation_deg", "opacity", "rebuild_notes"}], "doubts": []} |
| context.json | ext-context | the context object of the page JSON |
| text-a.json, text-b.json, text-c.json, text-final.json | ext-text-reader, vote-text.py | {"t1": "text", "t2": "text"} |
| second-read.txt and third-read.txt | vote-text.py | one block id per line |
| votes.json | vote-text.py | {"blocks": {"t1": {"text_status": "agreed", "read_agreement": 1.0, "other_readings": []}}, "unknown_words": [], "doubts": [], "needs_human": []} |
| leftovers.json | check-page.py | {"spots": [[left, top, right, bottom]]} |
| report.md | the main session, from the ext-verifier's reply | first line confidence: 95, then the mistakes and doubts |
| ocr.json | ocr-page.py | {"words": [{"text": "আমার", "box": [l, t, r, b], "confidence": 0.98}]} |
| blocks/t1.png ... | crop-blocks.py | cut-out text blocks for the ext-text-reader |

The crops in images/ (page_001_i1.jpg, page_001_i2.png and so on) are made by crop-images.py. They are output-bound files and are never deleted.

### The .md and .docx content

make-md.py and make-docx.py both build their file from the book JSON. The .docx is not built from the .md. Both hold, for each page:

- the page number;
- the background: its colour and its summary;
- the full context: page type, printed page number, headings, running header and footer, reading flow, links, languages and the layout summary, each on its own line;
- every text block in reading order, exactly as saved, with its type, box and style (font, size, bold, italic, colour, alignment). In the .docx the style is applied to the text itself;
- every image block: id, kind, crop file name, box, purpose and summary. Not the detailed description, style, colours or rebuild notes. Those stay in the JSON.

Neither file has scores or check notes. The review file is different: it is for checking, so it shows the detailed descriptions too.

```
# <book_name>

## Page 1

Background: colour #FFF8E7. <summary>
Context:
- Page type: lesson. Printed page number: 12. Languages: bn.
- Headings: t1. Running header: none. Running footer: none.
- Reading flow: t1, i1. Links: t1 label_of i1.
- Layout: <layout summary>

### t1 · heading
অ – অজগর
Style: SolaimanLipi, 36 pt, bold, colour #C0392B, left. Box: 90,70,550,150.

### i1 · drawing · images/page_001_i1.jpg
Box: 600,70,1040,420. Purpose: <purpose>.
Summary: <summary>
```

## Agents

The five agent files live in .claude/agents/: ext-text-reader.md, ext-layout-vision.md, ext-image-bg.md, ext-context.md, ext-verifier.md. There is no Boss agent: the main session runs the pipeline through the ext-run-book skill, which holds its rules.

- Each file starts with a header between two lines of three dashes, then the job. Header fields: name (the file name without .md), a short description (one line saying what the agent does, ending with "Use only when the main session names it for a page"), tools, model (see Model and effort) and, if the version knows the field, effort: medium and omitClaudeMd: true. With omitClaudeMd the agent does not load CLAUDE.md: everything it needs is in its own job text, which also keeps the ext-text-reader blind. ext-text-reader and ext-verifier also have skills: [bangla-text], so they get the Bangla text rules without CLAUDE.md.
- Tool limits are set in each agent's own file. The four workers (ext-text-reader, ext-layout-vision, ext-image-bg, ext-context) have tools: Read, Write. The ext-verifier has tools: Read only, so it cannot change any data: it replies with its report, and the main session saves it.
- The main session tells every run the page number, the exact file paths it may open and, for a worker, the exact file it must write. An agent opens only those paths and writes only that file. The main session always gives the full paths, with the workflow and book folders.
- Each run is a fresh run with no memory of any other run. A worker writes its file and replies with one line only ("done" or the problem), so 20 replies at once stay small.
- Each agent follows <wf>/config/schema.json for the shape of its file, except ext-text-reader, which sees only its block crops.
- Each worker writes only its own file, in work/page-XXX/: ext-layout-vision writes layout.json, ext-text-reader writes text-a.json, text-b.json or text-c.json (the main session says which run it is), ext-image-bg writes images.json, ext-context writes context.json. No agent edits a page JSON.

### ext-text-reader

You are a blind reader. Each run is a fresh run: you do not remember any other run. The main session gives you the exact block crops to read and the exact file name to write. Open only those crops and nothing else. Follow the bangla-text rules you were given. If a crop shows Latin letters where Bengali is expected (for example Pc, Rj, NU: the book's Bijoy font did not draw), copy those letters exactly. Do not turn them into Bengali yourself and do not guess: the vote script converts them with the conversion table. Type exactly what is printed, letter by letter, in the same language and script. Keep the line breaks. Do NOT fix spelling. Do NOT guess missing letters. Do NOT make the sentence sensible. Write the text in Unicode NFC. If a part is unreadable, write [?] there. Write the file the main session names (text-a.json, text-b.json or text-c.json) like this: {"t1": "text", "t2": "text"}.

### ext-layout-vision

Look at the page render (<wf>/temp/<book_name>/renders/page_XXX.jpg). Its size is in the page's entry in <wf>/temp/<book_name>/book-info.json. Never write any words. Find every text block (heading, body, caption, label, table_text, other) and give it a box in pixels of the render. Words inside an image block (table cells, chart or diagram labels, numbers on a number line, words in a screenshot) are text blocks too: list them, and do not skip them because they sit inside a picture. Add font size, bold, italic, colour, alignment, reading order, and lang: bn for Bengali text, en for English. A block of Latin letters inside Bengali text (for example Pc, Rj, NU, drawn when the book's Bijoy font is missing) is still bn. If a block's edges are unclear, add it to the "doubts" list. Write layout.json in the shape above. If the page has no text, still write it, with an empty text_blocks list.

### ext-image-bg

Look at the page render. Its size is in book-info.json. Find every image block: any picture, image or graphic object, of the kinds in Image blocks. Do not cut anything out and do not save any picture files: crop-images.py makes the crops. For each image block write: its box (in pixels of the render, tight around the whole block and nothing else), its kind, its layer (what sits on top of what), rotation and see-through level. Write a summary (one or two plain sentences: what it is and where it sits) and a detailed description in several sentences: what it shows, who or what is in it, where things sit inside it, the shapes, the colours as hex codes, line thickness and shading. For a chart, graph, table, map, timeline, infographic, maths model, parse tree or concept map, the description also gives its structure and the data it shows (axes, groups, values, trends, nodes and links, positions), because the crop and the description must be enough to rebuild it. The words inside an image block are text blocks, listed by someone else: do not copy them, only say what they are. Write a purpose (why it is on the page), the style (photo, cartoon, line drawing and so on), and rebuild notes (anything an artist needs to redraw it). Do the same, with a summary and a detailed description, for the page background colour or pattern, including a border around the page. Also give the background's boxes: the areas (in pixels of the render) where it has ink, such as the four border strips. The background gets no crop. Describe only the visual objects. Never write about the meaning of the page's text. Write only images.json, in the shape above. If the page has no image blocks, still write it, with the background and an empty images list.

### ext-context

Look at the page render. Read layout.json and images.json of the page: boxes, ids and kinds only, they hold no words. Write context.json with facts about the page, never what it means or teaches: page_type, printed_page_number (as printed, or empty), heading_ids (the text blocks that name the chapter, lesson or section the page belongs to), running_header_ids and running_footer_ids, reading_flow (the ids of all text and image blocks in the order a reader reads them), links (pairs of ids with a relation), languages (language codes used on the page) and layout_summary (one to three plain sentences: the number of columns, the regions such as header, body and footer, and where the image blocks sit in relation to the text). Use only ids that exist in layout.json and images.json, and only the values listed in File shapes. If the page has no text and no image blocks, still write it, with empty lists.

### ext-verifier

You did not make this data, and you cannot change it: you have read-only tools. Compare the page JSON with the page render line by line. Check every word, every image block (its box, kind, summary and description) and every style. Open each crop in images/ for this page and check that it shows the whole image block and nothing else. Check that context.json only uses ids that exist and that its layout summary matches the page. The render is small. If a word is too small to read, open its crop in work/page-XXX/blocks/. Also read votes.json and leftovers.json. Use the bangla-text rules you were given. Look hardest at blocks marked voted or unsure, and at unknown_words. Say if each leftover spot is a real miss. Reply with the report, and write no file. Its first line is exactly confidence: followed by a number from 0 to 100. Score like this: start at 100, subtract 5 for each wrong or missing word, 5 for each missing or wrongly placed block, image block or crop, and 2 for each wrong style, description detail or context fact. Never go below 0. After the first line, list the mistakes found and your doubts. Keep the whole report under 40 lines. Do not fix anything yourself.

## Skills

Each skill is a folder in .claude/skills/ with a SKILL.md. It starts with a header between two lines of three dashes, then the steps. The header has name, a one-line description, and an argument-hint. The four ext- skills change files, so set the header field that lets only the human start them (disable-model-invocation: true in the version checked). The text typed after the slash command reaches the skill as its argument. Every skill's first step is python shared/scripts/check-root.py. If it does not say ok, the skill stops. In the steps, RUN x.py means one plain command, python WF_book_extraction/scripts/x.py <book_name> plus the page number when the script takes one. Never put a variable in front of a command, and never join two commands with && or ;.

### ext-run-book

File: .claude/skills/ext-run-book/SKILL.md. Header: name: ext-run-book, argument-hint: <book_name> or all, and a description saying: runs the book extraction pipeline for one book or all books. The steps:

- Run check-root.py (see above).
- The argument is a book name, or all. Run python shared/scripts/common.py books WF_book_extraction to list the PDFs in input/ and in samples/WF_book_extraction/input/ with their book names. Stop if the name matches no PDF, or if two PDFs give the same book name. all means every book in input/, never the samples.
- If WF_book_extraction/output/<book_name>/ exists, the book is finished: stop and tell the human that a finished book is not run again, and that /ext-fix-book reopens it. For all, take every book that has no output/ folder, one after another. A sample book is never in output/, so it can always be run again.
- Read WF_book_extraction/config/run.json and render.json.
- Run cut-pages.py and check-text-layer.py. They only do the work that is missing, so this also resumes a stopped book: pages that are done in log.csv are skipped. If cut-pages.py stops because the PDF cannot be opened or has changed, tell the human its sentence and stop.
- Every page tagged render_failed in log.csv gets the note "This page could not be processed: the page could not be drawn." and the status done at once.
- Run the pipeline below, following the main-session rules.
- When every page is done, tell the human to read WF_book_extraction/temp/<book_name>/<book_name>_review.docx, fix every page under "A human must fix these" with /ext-correct, send other corrections the same way, and then type /ext-compile-book <book_name>.

Main-session rules (they live in this skill, so they cost nothing in other workflows):

- Work on one book at a time. Read the numbers from config/run.json and config/render.json. Never use a number from memory.
- Run the pages in batches and in parallel, in waves, as the pipeline says. Start every parallel run yourself. Do not rely on an agent starting another agent.
- Give every agent run the page number, the exact file paths it may open and, for a worker, the exact file it must write, and nothing else. For ext-text-reader, the paths are only the block crops in work/page-XXX/blocks/ (for run 2, only the blocks listed in second-read.txt, and for run 3, only the blocks listed in third-read.txt; you read these lists).
- The ext-verifier replies with its report. Save the reply, exactly as it is, as work/page-XXX/report.md with your own Write tool. If its first line is not confidence: followed by a number from 0 to 100, ask the verifier once more. If the second reply is no better, save confidence: 0 as the first line, followed by the reply. The page then counts as low.
- Every JSON file an agent writes is checked by the check-schema.py hook as it is saved. A bad file goes straight back to the agent, which fixes it, so there is no separate check. After a worker run, only make sure its file exists. If a script fails, or the file is missing, run that step again once. If it fails again, write one plain sentence in the note column ("This page could not be processed: ..."), set the page to done and go on. Its page then goes in the book as an empty page with that note.
- A page with low scores is run again once. Before the second try, run python WF_book_extraction/scripts/swap-try.py <book_name> <page> save. After the second try, run swap-try.py <book_name> <page> keep-better. Then mark the page done with a plain-words note.
- Change a page's status only with python shared/scripts/common.py set-status WF_book_extraction <book_name> <page> <status>. Empty a page's work folder only with python shared/scripts/common.py clear-work WF_book_extraction <book_name> <page>.
- When a page is done, run finish-page.py. It adds the review notes to the page JSON. Nothing is deleted.
- Never move or delete files in input/, temp/ or output/ yourself. The scripts do it, and a hook blocks your own commands.
- Use only these status names: new, extracted, redo, done.
- Keep log.csv as common.py creates it. Each script fills only its own columns in that page's row. The note column holds one plain sentence for the human when something needs a look (middle or low scores, unsure blocks, unknown words, a page that could not be processed). Leave it empty when all is well.
- Usage and rate limits: if a run stops because of a usage or rate limit (not a bad file), wait rate_limit.wait_s seconds and run it again, waiting twice as long each time, up to rate_limit.max_wait_s. This is not a failed try. If it happens twice in the same wave, halve max_parallel for the rest of the book. After rate_limit.max_retries waits for the same run, the plan's usage has probably run out: let the runs already going finish, start nothing new, and tell the human "Usage has run out. Resume later with the same command."
- Never stop to wait for a human, except when stop_after_same_note pages in a batch got the same kind of check note, or when usage has run out.
- Never skip a page. Never change config/schema.json. Never let one agent read another agent's answer, except the verifier.

Pipeline (names such as batch_size come from config/run.json):

```
START
  SET all_pages = the pages of the book
  FOR EACH batch IN all_pages:     # the first batch is a pilot of pilot_pages pages, then batch_size pages each
      SET live = the pages of the batch whose status is not "done"

      FOR EACH try IN [1, 2]:      # tries
          # Steps run as waves: a step runs for every page in live, up to max_parallel at the same time,
          # and ends for all pages before the next step starts (when every run has reported back).
          # The main session starts every parallel run itself.
          # The check-schema.py hook checks every JSON file an agent writes. If a script fails or a file is missing,
          # run that step again once for that page.
          # If it fails again: WRITE "This page could not be processed: ..." INTO log.csv note,
          # SET page.status = "done" (common.py set-status), and remove the page from live.
          # Usage or rate limit: wait and run again, as the main-session rules say. Not a failed try.
          # Only scripts move or delete files.

          FOR EACH page in live:
              RUN common.py clear-work                                 # empties work/page-XXX/, except try1/

          # (no Google OCR now: ocr-page.py is optional, only if config/ocr.json has enabled = true)
          WAVE agent ext-layout-vision on every page in live           # -> work/page-XXX/layout.json
          FOR EACH page in live WITH text blocks in layout.json:
              RUN crop-blocks.py                                       # -> work/page-XXX/blocks/t1.png ...
          WAVE agent ext-text-reader run 1 on every page WITH text blocks    # first Claude reading -> text-a.json (blind)
          FOR EACH page in live:
              RUN vote-text.py   # stage 1: compare run 1 with the PDF's own text, where it is usable
                                 # -> second-read.txt = blocks that disagree with the PDF text, or have no usable PDF text
                                 # (blocks that match are "agreed" and finished; a page with no text blocks gets
                                 # empty files and text_agreement 1.0)
          WAVE agent ext-text-reader run 2 on every page WITH a non-empty second-read.txt   # listed blocks only, fresh run -> text-b.json
          FOR EACH page that had run 2:
              RUN vote-text.py   # stage 2: -> third-read.txt = blocks still unresolved; text_agreement
          WAVE agent ext-text-reader run 3 on every page WITH a non-empty third-read.txt    # listed blocks only, fresh run -> text-c.json
          FOR EACH page that had run 3:
              RUN vote-text.py   # stage 3 -> text-final.json, votes.json
          WAVE agent ext-image-bg on every page in live                # -> work/page-XXX/images.json (with background boxes)
          FOR EACH page in live:
              RUN crop-images.py                                       # -> images/page_XXX_i1.jpg ...
          WAVE agent ext-context on every page in live                 # -> work/page-XXX/context.json
          FOR EACH page in live:
              RUN merge-page.py                                        # -> pages/page-XXX.json
              SET page.status = "extracted"                            # common.py set-status
              RUN check-page.py                                        # -> coverage (1.0 for an empty page), work/page-XXX/leftovers.json
          WAVE agent ext-verifier on every page in live                # replies with the report (first line: confidence: 95)
          FOR EACH page in live:
              IF the reply's first line is not "confidence: <0-100>":
                  ASK the verifier once more; IF still not: put "confidence: 0" in front of the reply
              WRITE the reply INTO work/page-XXX/report.md             # with the main session's own Write tool

          FOR EACH page in live:
              # good and low are the limits in scores. Middle = at or above low, below good.
              IF confidence, coverage and text_agreement are all at or above low AND the page has no latin_text tag:
                  SET page.status = "done"
                  IF any score is in the middle band, OR any block is "unsure", OR the page has doubts:
                      WRITE a plain-words check note INTO log.csv        # shown in the review file
              ELSE IF try == 1:
                  RUN swap-try.py save                    # moves the page JSON, its crops and its work files into work/page-XXX/try1/
                  SET page.status = "redo"                # the page stays in live for try 2
              ELSE:
                  RUN swap-try.py keep-better             # keeps the try with the higher confidence, with its scores
                  SET page.status = "done"
                  WRITE "Low scores after 2 tries. Read this page carefully." INTO log.csv note
              WRITE page, status, confidence, coverage, text_agreement INTO log.csv   # only through common.py, which locks it
              IF page.status == "done":
                  RUN finish-page.py   # adds the review notes to the page JSON. Deletes nothing
                  REMOVE the page from live

          IF live is empty:
              STOP the try loop

      RUN build-review.py         # -> <book_name>_review.docx (rebuilt after every batch, never while pages are running)

      IF stop_after_same_note OR MORE pages in this batch got a check note for the same reason:
          STOP starting new batches and tell the human why   # the agent instructions probably need a fix; runs already going finish first

  # human part: any time, no waiting
  HUMAN reads <book_name>_review.docx, "Look here first" pages first, and sends corrections
  FOR EACH correction:
      HUMAN types /ext-correct (a word, a crop, or run the page again)   # it edits the page JSON and rebuilds the review file
  HUMAN fixes every page under "A human must fix these" the same way   # /ext-compile-book refuses until they are fixed
  PICK pages for the spot-check: every_in_first in the first first_pages pages, then every_after
  HUMAN compares each with the original PDF
  IF any spot-checked page has mistakes: HUMAN fixes them, then checks 1 page in 10 instead
END
```

### ext-compile-book

File: .claude/skills/ext-compile-book/SKILL.md. Header: name: ext-compile-book, argument-hint: <book_name>, and a description saying: finishes a book, merges the pages, builds the .md and .docx and moves the book to output/. The steps:

- Run check-root.py.
- The argument is a book name. Stop if WF_book_extraction/temp/<book_name>/ is missing.
- Check that no page is tagged needs_human (if any are, stop and name them: a human fixes them with /ext-correct first), and that every page of the book is done in log.csv. If not, stop and name the pages. A page that is done but has no page JSON (it could not be processed) is allowed: it goes in the book as an empty page with the note "This page could not be processed."
- For a book that is not a sample: if WF_book_extraction/output/<book_name>/ already exists, the result becomes a new copy (see finalize-book.py). Nothing in output/ is ever replaced or deleted.
- Run merge-book.py: it writes <book_name>.json in temp/<book_name>/.
- Run make-md.py and make-docx.py: both build their file from the JSON.
- Count check: every text block id and image block id of every page appears exactly once in the JSON, in the .md and in the .docx, and every failed page appears once with its note. If anything is missing, stop and name it.
- Run python WF_book_extraction/scripts/finalize-book.py <book_name>. It copies the finished files into output/<book_name>/, or into the next free output/<book_name>_copy_N/, checks them, and only then deletes the book's temp folder. For a sample book it saves to, or compares with, samples/ instead of output/.
- Tell the human what finalize-book.py printed: where the files are, and the copy number if it made a new copy, or the sample comparison. Say that the result can now be committed in git.

### ext-fix-book

File: .claude/skills/ext-fix-book/SKILL.md. Header: name: ext-fix-book, argument-hint: <book_name>, and a description saying: reopens a compiled book so that a mistake can be fixed. The steps:

- Run check-root.py.
- The argument is a book name. Stop if WF_book_extraction/output/<book_name>/ is missing, or if WF_book_extraction/temp/<book_name>/ already exists (a run or a fix is already open).
- Tell the human what happens, and ask them to confirm: the finished output stays untouched; the newest version of the book (output/<book_name>/ or its highest _copy_N) is reopened in temp/<book_name>/; compiling it again makes a new copy, and nothing in output/ is replaced.
- Run reopen-book.py.
- Tell the human to send corrections with /ext-correct, to read the rebuilt review file, and then to type /ext-compile-book <book_name> when they are happy.

### ext-correct

File: .claude/skills/ext-correct/SKILL.md. Header: name: ext-correct, argument-hint: <book_name> <page> <what>, and a description saying: fixes one page of a book: a wrong word, a wrong crop, or running the page again. Corrections are steps needed only sometimes, so they live here and not in CLAUDE.md. The steps:

- Run check-root.py.
- The arguments are a book name, a page number and what to do: <block id>: <the right text> (for example t3: আমার), crop <image id> (for example crop i1), or again. If WF_book_extraction/temp/<book_name>/ is missing because the book is already compiled, stop and say: "Type /ext-fix-book <book_name> first."
- A wrong word: in temp/<book_name>/pages/page-XXX.json, replace the text of that block with the text the human gave, exactly as given, add "Corrected by the human." to its doubts, and remove its unconverted-symbol doubt. If no flagged block is left on the page, run python shared/scripts/common.py remove-tag WF_book_extraction <book_name> <page> needs_human. Then run build-review.py.
- A wrong crop: look at the page render and the crop, fix the box of that image block in the page JSON, run crop-images.py <book_name> <page>, then build-review.py. If it is not clear what is wrong, ask the human first.
- Run again: run python shared/scripts/common.py set-status WF_book_extraction <book_name> <page> new, then tell the human to type /ext-run-book <book_name>.
- Tell the human what changed.

## Scripts

Shared scripts are in shared/scripts/. Workflow scripts are in <wf>/scripts/. All follow the script rules below and use common.py. They read their numbers from <wf>/config/.

### Script rules

- Python 3.11. One script does one job. File names are kebab-case, except common.py.
- Arguments: a script that works on a book gets the book name as its first argument, and a script that works on one page gets the page number as its second, for example python WF_book_extraction/scripts/crop-blocks.py math_book_pp 7 (that is page_007 and page-007). cut-pages.py and check-text-layer.py work on the whole book unless given a page number. The book is never passed in an environment variable, because allow rules do not match a command that starts with a variable assignment.
- Finding things: every script finds the repo root by going up from its own folder until it meets the folder that holds shared/ and CLAUDE.md. A workflow script finds its workflow as the folder above its own scripts/ folder. It adds <root>/shared/scripts to its import path and imports common. A script never guesses between books.
- Shared helper: folder paths, page names, the book name, log.csv, the work folders and file checks come from shared/scripts/common.py. Never write them again in another script. Always call the page name functions, and never build a name like page-007 by hand. Every book-specific path is built from the book name, so a script never touches another book's files.
- Many at once: many copies of a script may run at the same time, each for a different page. A script writes only inside its own page's files, and changes log.csv only through common.py, which locks it.
- Book-wide files: book-info.json and pdf-words.json are written once, before any page is processed, and only if they do not exist yet. No other script writes them.
- Safe to run again: a script may overwrite its own files, never another script's files. It writes to a temporary name first and then renames, so a crash never leaves a half-written file.
- Moving and deleting: only scripts move or delete files. During a run, only common.py clear-work and swap-try.py do it, and only inside one page's work folder and crops. Only finalize-book.py deletes a book's temp folder, after it has copied and checked the finished files.
- Boxes: a box that reaches past the page edge is cut back to the page. A box with no area left is skipped, and the script adds a doubt to that page's note.
- Empty pages: a page with no text or no image blocks still gets its file, with an empty list inside.
- Errors: on an error a script prints one plain sentence, writes it in the note column of that page's row, and stops with an error code. Errors that need the human (a PDF that cannot be opened or has changed) stop the whole book with one plain sentence that says what to do.
- Check before finishing: every JSON file a script saves is checked against <wf>/config/schema.json.
- log.csv: each book has its own, at temp/<book_name>/log.csv, with one row per page and these columns: page, status, confidence, coverage, text_agreement, tags, note. Scripts write short machine labels (like over_500kb or render_failed) in tags. note is only for one plain sentence meant for the human. A script fills only its own columns. A page's status lives only here, and only the main session sets it (with common.py set-status).
- Report: when it ends, a script prints one line saying what it did.

### common.py (Shared)

- Paths: the root is found as the script rules say. Fixed: <root>/input/, <root>/shared/reference/, and for a workflow <root>/samples/<wf>/input/ and <root>/samples/<wf>/output/. For a workflow: config/, temp/<book_name>/ with renders/, pages/, images/, work/, book-info.json, pdf-words.json, log.csv and <book_name>_review.docx, and output/. For one page: work/page-XXX/.
- Page names: internal_page_name(n) turns 7 into page-007 (for pages/ and work/), and output_page_name(n) turns 7 into page_007 (for renders and crops). Both can be turned back into the number.
- Choosing the book: the book name is the first argument of the script. pdf_for_book(book_name) finds the PDF in input/ whose book name matches, and for a name that starts with sample_ it looks in samples/<wf>/input/. is_sample(book_name) says whether it is a sample. If no PDF matches, the script stops with the plain sentence "No PDF gives the book name <book_name>." If two PDFs give the same book name, it stops with "Two PDFs give the same book name (<book_name>): <first pdf> and <second pdf>. Rename one of them."
- config(name) returns the content of <wf>/config/<name>.json.
- log.csv functions: create it in temp/<book_name>/ with the columns above if it is missing, and read or update only the given columns of one page's row. Every change is locked: create log.csv.lock so that only one process can create it (exclusive create), wait up to log_lock.wait_s seconds for it if another script holds it, then read the file, change the row, write a temporary file, rename it over log.csv, and delete the lock. A lock older than log_lock.stale_s seconds is left over from a crashed script: delete it and go on.
- validate(file_path) checks a saved JSON file against its definition in the workflow's config/schema.json (the workflow comes from the path, and the kind from the path and file name, so layout.json is a layout file).
- save_json(path, data) writes to a temporary name and then renames.
- fail(page, sentence) prints the sentence, writes it in the note column of that page's row, and stops with an error code.
- book_info(page) returns one page's entry from book-info.json. pdf_words(page) returns one page's words from pdf-words.json, or nothing if the page has none. pdf_fingerprint(path) returns the SHA-256 of the PDF file.
- clear_work(page) creates the page's work/page-XXX/ folder if it is missing and empties it, except its try1/ folder.
- set_status(page, status) writes one of the four status names into that page's row. add_tag(page, tag) and remove_tag(page, tag) change one page's tags.
- bijoy_to_unicode(text) converts Bijoy (SutonnyMJ and other legacy ANSI Bengali fonts) to Unicode Bengali with one conversion table, taken from a maintained open-source converter. Tell the human its name and licence before using it, and add it to the install list. This is the only place the conversion is written: check-text-layer.py and vote-text.py both call it. If it crashes on a word, it adds a trailing space and tries again (removing the space after), and if it still fails it returns the word unchanged.
- is_bijoy_latin(text) says whether a text of a Bengali block holds Latin letters, so it must be converted. leftover_symbols(text) lists the words of Bengali text that still hold an ASCII sign after conversion.

Run by itself, each as one plain command:

- python shared/scripts/common.py validate <file_path> checks one file and prints ok or the problem.
- python shared/scripts/common.py books <wf> lists every PDF in input/ and in samples/<wf>/input/ with its book name, and reports any two PDFs that give the same book name.
- python shared/scripts/common.py clear-work <wf> <book_name> <page> empties that page's work folder, except try1/.
- python shared/scripts/common.py set-status <wf> <book_name> <page> <status> sets a page's status.
- python shared/scripts/common.py add-tag <wf> <book_name> <page> <tag> and remove-tag (same arguments) change a page's tags.

### check-root.py (Shared)

Checks that Claude Code was started at the root of ICAF_workflows: the current folder holds CLAUDE.md, .claude/settings.json, shared/ and input/. If not, it prints "Open Claude Code at the ICAF_workflows folder, then try again." and stops with an error code. Otherwise it prints ok. Every skill runs it as its first step, so the check is written once.

### cut-pages.py

Opens the book's PDF (found as in common.py, item 3). If the PDF cannot be opened (damaged, or locked with a password), it stops before making any folder, with the sentence "The PDF <file> cannot be opened. It may be damaged or locked with a password. Replace it and run again." On the first run it saves the PDF's fingerprint (pdf_sha256) in book-info.json. On a later run, if the fingerprint no longer matches, it stops with "<file> has changed since this book was started. Put the old PDF back, or delete temp/<book_name>/ by hand to start again."

It renders every page that has no render yet, as temp/<book_name>/renders/page_001.jpg: a JPEG (not a PNG) at the sizes in config/render.json (page_render): about long_side_px on the long side and under max_kb KB. Start at long_side_px and jpeg_quality. If the file is too big, lower the quality step by step (never below min_jpeg_quality), then the size step by step (never below min_long_side_px). If it is still too big, keep the smallest version and add the tag over_500kb to that page's row in log.csv. If one page cannot be drawn, it goes on with the next page and adds the tag render_failed to that page's row. When a page number is given, it renders that page again even if a render exists. It writes temp/<book_name>/book-info.json once, only if the file does not exist yet, with pdf_sha256, and width, height, scale (PDF points to pixels) and file_size_kb for every page that was drawn. Prints how many pages were rendered, how many are too big and how many could not be drawn.

### check-text-layer.py

If pdf-words.json already exists, it does nothing. Otherwise, for each page of the book, it reads the PDF's hidden text layer as words with box positions, and multiplies the positions by the page's scale in book-info.json so they match the render. Then, in this order, following the Bangla text rules:

- If the words are clearly real Bangla Unicode letters in the right order, use them as they are.
- Otherwise treat them as Bijoy/ANSI text and convert each word to Unicode with a Bijoy-to-Unicode converter. Use bijoy_to_unicode() from common.py. Never reject text before this step.
- Check the converted text. Never discard it. If it still looks wrong, save it anyway and mark that page "doubt": true, so it stays in the vote and the problem is shown to the human.
- Clean the words that pass (Unicode NFC, one kind of space) and save them for that page in pdf-words.json. The file is written once, after the last page.

If the text layer is empty or unreadable, add the tag no_text_layer to that page's row and save nothing for that page. That page then has no PDF text, and every block on it gets a second Claude reading.

### ocr-page.py (optional)

Runs only if config/ocr.json has enabled: true. Input: the book name and a page number. Draws that page of the PDF at the dpi in config/ocr.json, sends it to the engine named there (Google Cloud Vision, with the language_hints), and saves every word with its box and confidence to work/page-XXX/ocr.json. Scales the boxes to match the render, using the page's entry in book-info.json. If the google-cloud-vision package is missing, tells the human to run pip install google-cloud-vision first.

### crop-blocks.py

Input: the book name and a page number. Reads work/page-XXX/layout.json (its boxes are in pixels of the render) and the page's entry in book-info.json. If layout.json has no text blocks, makes no crops and stops without an error. Boxes are cut back to the page as the script rules say. For every text block, cuts that area out of the ORIGINAL PDF page, drawn at block_crop.dpi (not out of the small render), with extra space around it of block_crop.padding_px px of the render. Saves them as work/page-XXX/blocks/t1.png, t2.png and so on. These are working files for the ext-text-reader.

### vote-text.py

Input: the book name and a page number. It runs in up to three stages, and the stage depends on which files exist in the page's work/page-XXX/ folder: only text-a.json is stage 1, text-b.json as well is stage 2, and text-c.json as well is stage 3. If layout.json has no text blocks, save text_agreement 1.0 in log.csv, write an empty text-final.json and votes.json and stop. Otherwise compare the texts word by word (Python's difflib). The readers are: text-a.json (the first blind Claude reading, run 1); text-b.json and text-c.json (the second and third Claude readings, only for the blocks that needed them); the PDF's own text for the page, from pdf-words.json (each word goes into the text block whose box it sits in, in reading order); and ocr.json in the same way, if it exists (only when Google OCR was used, and counted as one more reader in stages 2 and 3).

- A block id that a reader's file does not have counts as [?] for that reader, so the block goes on to the next reading. Bijoy first: a block counts as bn if ext-layout-vision said bn, or if its PDF text on this page is converted Bijoy text (the font did not draw, so the crop may look English). For every such block, a reader's text that holds Latin letters is Bijoy code. Convert it with common.bijoy_to_unicode() before anything else, and note bijoy_converted and lang: bn for that block in votes.json (merge-page.py uses this lang over the layout's). A Latin-letter text is never used as it is. Clean all texts the same way before comparing: Unicode NFC, one kind of space, one kind of quote mark and dash. Never change letters. The PDF's own text is cleaned in the same way.
- Usable PDF text: a block has usable PDF text if the page has words in pdf-words.json, words sit inside the block's box, and after cleaning the text is real Bangla Unicode (or converted Bijoy text, also when it is marked doubt, from check-text-layer.py). A block without usable PDF text goes straight to a second reading (3.2).
- Stage 1 (only text-a.json exists):
  - 3.1 A block with usable PDF text: compare text-a with the PDF's text. If they match, the block is agreed and is finished: it needs no more readings. If they differ, list the block id in second-read.txt (one block id per line). This is 3.1.1: a disagreement with the PDF's text always triggers a second Claude reading.
  - 3.2 A block without usable PDF text: list the block id in second-read.txt.
  - If second-read.txt is empty, write text-final.json and votes.json now.
- Stage 2 (text-b.json exists, text-c.json does not). text-b.json holds only the blocks listed in second-read.txt.
  - A block with usable PDF text (3.1.1): the readers are text-a, text-b and the PDF's text. If at least 2 of them match, mark the block voted and keep that version. If all three differ, list the block id in third-read.txt.
  - A block without usable PDF text (3.2): if text-a and text-b match, mark the block agreed. If they differ, list the block id in third-read.txt.
  - If third-read.txt is empty, write text-final.json and votes.json now.
- Stage 3 (text-c.json exists, only for the blocks in third-read.txt): the readers are text-a, text-b, text-c and, if the block has usable PDF text, the PDF's text and ocr.json (one reader each). For each differing word keep the version that the most readers match, if at least 2 readers match it and no other version has as many readers. Mark the block voted. Otherwise (no version has 2 readers, or two versions have the same number) mark the block unsure and keep text-a's word with [?] in front. Then write text-final.json and votes.json.
- Other readings: for every block marked voted or unsure, write the readings that lost in other_readings in votes.json (each with its reader: text_a, text_b, text_c, pdf or ocr).
- Scores: save text_agreement once, as soon as every block has its first comparison: at stage 1 when second-read.txt is empty, otherwise at stage 2. The first comparison of a block is text-a against its usable PDF text, or against text-b when it has none. text_agreement = 1 minus (differing characters in the first comparisons divided by all characters), saved into log.csv. Also save each block's read_agreement (the share of words that match in its first comparison, 0 to 1) in votes.json.
- Leftover symbols: if a word in a bn block of text-final still holds an ASCII sign (such as ' or a Latin letter) after conversion, add "<block id>: unconverted symbol in <word>" to doubts in votes.json, add the block id to needs_human in votes.json, and add the tag needs_human to that page's row in log.csv. Then check every word against shared/reference/bangla-words.txt and list the words not found as unknown_words in votes.json.

### crop-images.py

Input: the book name and a page number. Reads work/page-XXX/images.json (its boxes are in pixels of the render) and the page's entry in book-info.json. If images.json is missing (the page is done and its working files were moved or emptied), it reads the image blocks from pages/page-XXX.json instead, so a wrong box can be fixed there and the crop made again. If there are no image blocks, makes no crops and stops without an error. Boxes are cut back to the page as the script rules say. For every image block, cuts that area out of the ORIGINAL PDF page, drawn at image_crop.dpi (not out of the small render), with extra space around it of image_crop.padding_px px of the render. Saves it as temp/<book_name>/images/page_XXX_ plus the block id and the file type, for example page_001_i1.jpg. Save the kinds in image_crop.jpeg_kinds as JPEG at image_crop.jpeg_quality. Save the other kinds (the line-art kinds: diagram, chart, graph, table, map, timeline, infographic, maths model, model, parse tree, concept map, screenshot) as PNG, so that thin lines and small words stay sharp. If a file is over image_crop.max_kb KB, lower the size step by step (never below image_crop.min_long_side_px on the long side), and for JPEG also the quality (never below image_crop.min_jpeg_quality). If it is still too big, keep the smallest version and add the tag image_over_1mb to that page's row in log.csv.

### merge-page.py

Input: the book name and a page number. Reads layout.json, images.json, context.json, text-final.json and votes.json (all in work/page-XXX/) and joins them into pages/page-XXX.json in the config/schema.json shape: the size and text blocks come from layout.json (each block gets its text from text-final.json, and its text_status, read_agreement and other_readings from votes.json), the background and image blocks come from images.json (each image block also gets file, the name of the crop file that exists for it (.jpg or .png) in images/), context comes from context.json, unknown_words come from votes.json, and the doubts of layout.json and images.json are put together with the doubts in votes.json. Fills overlaps_text for every image block with the ids of the text blocks whose boxes overlap the block's box. If any file is missing, uses fail() and stops. At the end it checks the page JSON against config/schema.json.

### check-page.py

Input: the book name and a page number. Two checks, plain maths, no AI.

- Coverage: take the render renders/page_XXX.jpg and paint over every text box, every image block box and every box in background.boxes from the page JSON. Count the ink that is left (anything clearly different from the page background colour). Coverage = ink inside boxes divided by all ink. 1.00 means nothing was missed. If the page has no ink outside the background at all (an empty page), coverage is 1.00. Saves every leftover ink spot as a box in work/page-XXX/leftovers.json. Writes coverage into log.csv.
- Latin check: for every text block with lang: bn in the page JSON (and every block whose PDF text on this page is converted Bijoy text, whatever its lang says), count its letters (not digits, spaces or punctuation). If 80% or more of them are Latin letters (A–Z, a–z), add the tag latin_text and the note "<block id>: Bengali text is still in Latin letters (Bijoy not converted)." to the page's row. Otherwise remove the tag latin_text if it is there.

### finish-page.py

Input: the book name and a page number. The main session runs it when a page is done. It reads the first line of work/page-XXX/report.md (the confidence; if the first line is not confidence: plus a number from 0 to 100, it uses fail()), the text after that first line (the verifier's notes), leftovers.json, the page's coverage and text_agreement in log.csv, and whether work/page-XXX/try1/ exists (tries is 2 if it does, otherwise 1). It adds them to pages/page-XXX.json as review, and checks the page JSON against config/schema.json. If the page's row has the tag latin_text (it stayed after 2 tries), it adds the tag needs_human. It deletes nothing. If anything fails, it uses fail() and leaves everything as it is.

### build-review.py

Input: the book name. Builds temp/<book_name>/<book_name>_review.docx, the file the human checks. Reads every pages/page-XXX.json in page order and log.csv.

- At the top, one line of progress, for example "120 of 200 pages done". A page that is done but has no page JSON (it could not be processed) is listed under "Pages that could not be processed", with its note. Pages not done yet are not listed. Above everything, a list called "A human must fix these" names every page tagged needs_human, with its doubts.
- At the top, a short list called "Look here first" with the page numbers that have check notes.
- For each page: the page number and size; the background (colour, detailed description, rebuild notes); the full context in plain words; every text block in reading order, with the text exactly as saved (never fix, change or shorten any word), and one short line under it with its box, text_status and style; and every image block with its id, crop file name, box, layer, rotation, opacity, overlaps_text, kind, summary, detailed description, purpose, style, main colours and rebuild notes. This file is for checking, so it shows all the detail.
- Under each page title: its scores (review.confidence, review.coverage, review.text_agreement) and its check notes in plain words: the note from log.csv, the doubts, the unknown_words, every block marked voted or unsure (with its text and its other_readings), the number of review.leftover_spots, and review.checker_notes.
- Apply each text block's saved style (bold, italic, colour, size, alignment), use a Bangla font such as Noto Sans Bengali, and start each page on a new page. Do not embed the crops: show their file names as plain text.
- If the file already exists, replace it. If it cannot be replaced because it is open in Word, save the new version next to it with _latest added to the name (for example <book_name>_review_latest.docx) and tell the human.

### merge-book.py

Input: the book name. Reads the pages of the book in page order. A page with pages/page-XXX.json is added as it is. A page with no page JSON (it could not be processed) is added in the short form {"page": 7, "failed": true, "note": "This page could not be processed."}. Writes temp/<book_name>/<book_name>.json in the shape of the Book JSON and checks it against config/schema.json.

### make-md.py

Input: the book name. Reads <book_name>.json and writes <book_name>.md in the layout in The .md and .docx content. The text of every block is written exactly as saved. The image blocks and the background show their short summary, not the detailed description. The full context is written for every page. A failed page is written as its page number and the line "This page could not be processed." No scores and no check notes.

### make-docx.py

Input: the book name. Builds <book_name>.docx from <book_name>.json, not from the .md. It holds the same content as the .md, with each text block styled as saved (font, size, bold, italic, colour, alignment). Use a Bangla font such as Noto Sans Bengali, and start each page on a new page. Do not embed the crops: show their file names as plain text. A failed page is a page with only its number and the line "This page could not be processed." No scores and no check notes. After writing, read it back and check that every text block id and image block id appears exactly once.

### reopen-book.py

Input: the book name. Reopens a compiled book. Below, output/<book_name>/ means its newest version: the highest output/<book_name>_copy_N/, or output/<book_name>/ if there is no copy (its book files may carry the _copy_N name). It stops if output/<book_name>/ is missing, or if temp/<book_name>/ already exists. It copies, and never moves, from output/<book_name>/ into temp/<book_name>/: images/, renders/ and log.csv. It splits <book_name>.json into one pages/page-XXX.json per page (the review section stays). It rebuilds book-info.json (from the renders) and pdf-words.json (as check-text-layer.py does). It adds the tag reopened to every page's row in log.csv, keeps each page's status, and builds the review file with build-review.py. It never touches output/ and deletes nothing.

### swap-try.py

Input: the book name, a page number, and save or keep-better. The main session runs it for a page with low scores.

- save (before the second try): writes the page's confidence, coverage and text_agreement from log.csv into work/page-XXX/try1/scores.json, then moves the page JSON (pages/page-XXX.json), the page's crops (images/page_XXX_*) and every file in work/page-XXX/ except try1/ into work/page-XXX/try1/.
- keep-better (after the second try): compares the confidence in work/page-XXX/report.md with the one in try1/report.md. If the first try is higher, it deletes the second try's page JSON and crops, moves the first try's files back, and writes the first try's scores into log.csv. Otherwise it leaves the second try as it is. Either way try1/ stays until the book is final, so tries is 2.

It never touches another page.

### finalize-book.py

Input: the book name. Only the compile skill runs it, after the count check. It never replaces or deletes anything in output/.

- A normal book: the target is output/<book_name>/ if it does not exist yet, otherwise the next free output/<book_name>_copy_N/ (N = 1, 2, 3 ...). Inside a copy, the three book files are named after the folder (<book_name>_copy_N.json, .md and .docx), so no .docx is ever replaced. It copies (never moves) into the target: the book files, log.csv, renders/ and images/. It checks that every file arrived with the same size. Only then does it delete temp/<book_name>/. If anything fails, it deletes the half-made target folder (nothing else), leaves temp/ as it is, and stops with one plain sentence.
- A sample book (name starts with sample_): it never writes to output/. If samples/<wf>/output/<book_name>/ is missing, it copies the same files there and prints "Saved as the sample answer. Check it by hand before you commit it." Otherwise it compares the new Book JSON with the saved one: the page count, the text of every text block by id, and the number and kind of image blocks on each page. It prints every difference in plain words, or "No differences.", and writes nothing to samples/. To change a saved answer, the human replaces it by hand. Then it deletes temp/<book_name>/.

### Tests

After any change, run the sample: /ext-run-book sample_book, then /ext-compile-book sample_book. The compile step compares the result with samples/WF_book_extraction/output/sample_book/ and lists every difference. Test /ext-fix-book on a small real book: compile it, reopen it, change one word with /ext-correct, compile again, and check that the first version is untouched and the new one is in output/<book_name>_copy_1/. For every test, ask Claude Code to show the command it ran and its output as evidence.

## Adding another workflow (Shared)

- Make WF_<name>/ with config/, scripts/, temp/ and output/. The .gitignore pattern already covers WF_*/temp/.
- Write its build pack as specs/WF_<name>.md, and add samples/WF_<name>/{input,output}/.
- Add its agents and skills to .claude/agents/ and .claude/skills/, all with its own prefix, each with a one-line description. Its skills start with check-root.py. Add one line for it to the allow rules in .claude/settings.json: Bash(python WF_<name>/scripts/*). The Edit(/WF_*/temp/**) rule and the deny rules already cover it.
- Reuse the Shared parts. Do not copy them.
- When there are more than about 5 workflows, turn each into a plugin.

