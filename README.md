# ICAF Workflows

ICAF Workflows is a collection of Python workflows for processing books and related
documents. The repository currently includes a book-extraction workflow that renders
PDF pages, extracts text, performs OCR when needed, reviews page results, and compiles
finished books into Markdown and Word documents.

## Workflows

- **`WF_book_extraction`** - Extract and review book content from PDF files.
- **`WF_book_review`** - Book-review workflow documentation is maintained in
  `specs/WF_book_review.md`.

## Requirements

- Python 3.13 or a compatible recent Python 3 version
- Git
- Python dependencies listed in `requirements.txt`

Install dependencies from the repository root:

```text
pip install -r requirements.txt
```

The repository includes a local virtual environment in `env/` for the current
workspace. Activate it on Windows if you want to use that environment:

```powershell
.\env\Scripts\Activate.ps1
```

## Book extraction

Place source PDFs in:

```text
WF_book_extraction/input/
```

Book names are derived from PDF filenames in snake_case. The sample input is in
`samples/WF_book_extraction/input/`.

The preferred interface is the Claude Code workflow commands:

```text
/ext-run-book <book_name>
/ext-correct <book_name> <page> <what>
/ext-compile-book <book_name>
/ext-fix-book <book_name>
```

Use `/ext-run-book all` to process every unfinished book in the main input folder.
Finished books are written to `WF_book_extraction/output/`. Recompiling a finished
book creates a new `_copy_N` directory rather than replacing an existing result.

For direct script work, run commands from the repository root with `python` and
provide the book name as required by the script. For example:

```text
python WF_book_extraction/scripts/crop-blocks.py <book_name> 7
```

Before using a workflow, verify that the command is being run from the repository
root:

```text
python shared/scripts/check-root.py
```

## Repository layout

```text
WF_book_extraction/
  config/       Workflow configuration and JSON schema
  input/        Source PDFs (read-only)
  output/       Finished books and generated deliverables
  scripts/      Pipeline and review scripts
  temp/         Working files created during processing
shared/
  reference/    Shared reference data
  scripts/      Shared validation and utility code
samples/        Sample workflow inputs and expected outputs
specs/          Workflow build packs and design records
.claude/        Claude Code skills, agents, rules, and settings
```

## File-handling rules

- Treat `input/` as read-only.
- Do not manually move or delete files in workflow `input/`, `temp/`, or `output/`
  directories; use the provided scripts and workflow commands.
- Do not replace existing output. A new compilation should be saved as a new copy.
- Human contributors commit generated results to Git.

## Configuration

Book extraction settings are in `WF_book_extraction/config/`:

- `run.json` - pipeline behavior
- `render.json` - page rendering
- `ocr.json` - optional OCR configuration
- `schema.json` - generated JSON validation schema

Google Cloud Vision is optional and is only needed when OCR is enabled in
`ocr.json`.
