# Naming rules

Follow these for every file, folder, script, JSON key and column.

- Output-bound files are snake_case: every file that ends up in an output/ folder, from the moment
  it is made. These are the renders (page_001.jpg), the crops (page_001_i1.jpg), <book_name>.json,
  <book_name>.md, <book_name>.docx and log.csv.
- Every other file Claude builds is kebab-case (lowercase words joined by hyphens): scripts
  (cut-pages.py), hooks, agent files (ext-text-reader.md), skill folders (ext-run-book/), rule files,
  reference files (bangla-words.txt), and the working files in temp/ (book-info.json, pdf-words.json,
  pages/page-001.json, work/page-001/, text-a.json, second-read.txt).
- Prefixes: every agent and skill name starts with its workflow's prefix (ext-, rev-). There is no
  unprefixed agent or skill. (bangla-text is the one shared reference skill, used by all workflows.)
- Names the human chose stay as they are: ICAF_workflows, the workflow folders (WF_book_extraction),
  specs/WF_book_extraction.md, <book_name>_review.docx, and the sample_ start of a sample book's name.
  Tool names stay as they are: CLAUDE.md, CLAUDE.local.md, SKILL.md, .claude/, settings.json,
  settings.local.json, .gitignore, log.csv.lock, requirements.txt. common.py is one word and is
  imported by the other scripts, so it has no hyphen. A script whose name has a hyphen can be run
  but not imported.
- Data is always snake_case: JSON keys, CSV columns and fixed values (text_status, maths_model,
  unsure), even inside kebab-case files.
- Python code: variables and functions in snake_case, classes in PascalCase, constants in
  UPPER_SNAKE_CASE (PEP 8).
- Page numbers have at least 3 digits. Output-bound names use page_001, and internal names use
  page-001. XXX stands for the page number.
- Placeholders are written in angle brackets, in snake_case: <book_name>, <wf>.
- Book name: the PDF's file name without .pdf, changed to snake_case: lowercase English letters,
  spaces and hyphens become _, Bangla letters stay, and any other character becomes _ (repeated _
  are joined into one, and _ at the start or end is dropped). Example: Math-Book-PP.pdf gives
  math_book_pp. Only common.py computes it (python shared/scripts/common.py books <wf>).
