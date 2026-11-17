---
name: ext-run-book
description: Runs the book extraction pipeline (WF_book_extraction) for one book or all books, page by page in waves.
argument-hint: <book_name> or all
disable-model-invocation: true
---

# /ext-run-book $ARGUMENTS

Below, BOOK is the book name, `WF` is `WF_book_extraction`, and RUN x.py means one plain command
with the Bash tool: `python WF_book_extraction/scripts/x.py BOOK` plus the page number when the
script takes one. Never put a variable in front of a command, and never join two commands with &&
or ;. Every command below is typed exactly like that, with BOOK and the page replaced.

## Steps

1. Run `python shared/scripts/check-root.py`. If it does not print `ok <root folder>`, stop and tell
   the human its sentence. Remember the root folder: agent briefs use full paths under it.
2. The argument is a book name, or `all`. Run `python shared/scripts/common.py books WF_book_extraction`.
   It lists every PDF in input/ and in samples/WF_book_extraction/input/ with its book name. Stop if
   the name matches no PDF, or if it reports two PDFs with the same book name (ask the human to
   rename one). `all` means every book in input/ that is not finished, never the samples.
3. If `WF_book_extraction/output/BOOK/` exists, the book is finished: stop and tell the human that a
   finished book is not run again, and that /ext-fix-book BOOK reopens it. For `all`, take every
   book that has no output/ folder, one after another, each through steps 4 to 8.
4. Read `WF_book_extraction/config/run.json` and `WF_book_extraction/config/render.json`. Use only
   these numbers, never a number from memory.
5. RUN cut-pages.py, then RUN check-text-layer.py. They only do the work that is missing, so this
   also resumes a stopped book: pages that are done in log.csv are skipped. If cut-pages.py stops
   because the PDF cannot be opened or has changed, tell the human its sentence and stop.
6. RUN `run-plan.py BOOK status`. Every page listed as render_failed and not done: run
   `python shared/scripts/common.py set-note WF_book_extraction BOOK <page> "This page could not be processed: the page could not be drawn."`
   and `python shared/scripts/common.py set-status WF_book_extraction BOOK <page> done`.
7. Run the pipeline below, following the main-session rules.
8. When every page is done, tell the human to read
   `WF_book_extraction/temp/BOOK/BOOK_review.docx`, fix every page under "A human must fix these"
   with /ext-correct, send other corrections the same way, and then type /ext-compile-book BOOK.

## Main-session rules

- Work on one book at a time. Pages of two books never run at the same time.
- Run the pages in batches and in parallel, in waves, as the pipeline says. Start every parallel run
  yourself, with several Agent tool calls in one message (up to max_parallel at once; if the session
  allows fewer, run as many as it allows and queue the rest). Do not rely on an agent starting
  another agent. A wave ends when every run of its step has reported back.
- Give every agent run exactly the brief that `run-plan.py BOOK brief <page> <agent> [run]` prints,
  and nothing else: it holds the page number, the full paths it may open and, for a worker, the one
  file it must write. If the brief says `skip: ...`, do not start that run.
- Never let one agent read another agent's answer, except the verifier. The ext-text-reader gets
  only block crops.
- The ext-verifier replies with its report. Save the reply, exactly as it is, as
  `WF_book_extraction/temp/BOOK/work/page-XXX/report.md` with your own Write tool. If its first line
  is not `confidence:` followed by a number from 0 to 100, ask the verifier once more (a fresh run
  with the same brief). If the second reply is no better, save `confidence: 0` as the first line,
  followed by the reply. The page then counts as low.
- Every JSON file an agent writes is checked by the check-schema.py hook as it is saved; a bad file
  goes straight back to the agent, which fixes it. After a worker run, only make sure its file
  exists. If a script fails, or the file is missing, run that step again once for that page. If it
  fails again: `python shared/scripts/common.py set-note WF_book_extraction BOOK <page> "This page could not be processed: <what failed>."`,
  then `python shared/scripts/common.py set-status WF_book_extraction BOOK <page> done`, and remove
  the page from live. It goes in the book as an empty page with that note.
- Change a page's status only with
  `python shared/scripts/common.py set-status WF_book_extraction BOOK <page> <status>`. Use only
  these status names: new, extracted, redo, done. Empty a page's work folder only with
  `python shared/scripts/common.py clear-work WF_book_extraction BOOK <page>`.
- Keep log.csv as common.py creates it. Only scripts write it.
- Never move or delete files in input/, temp/ or output/ yourself. The scripts do it, and a hook
  blocks your own commands. Never change config/schema.json. Never skip a page.
- Usage and rate limits: if a run stops because of a usage or rate limit (not a bad file), wait
  rate_limit.wait_s seconds and run it again, waiting twice as long each time, up to
  rate_limit.max_wait_s. This is not a failed try. If it happens twice in the same wave, halve
  max_parallel for the rest of the book. After rate_limit.max_retries waits for the same run, the
  plan's usage has probably run out: let the runs already going finish, start nothing new, and tell
  the human "Usage has run out. Resume later with the same command."
- Never stop to wait for a human, except when batch-check says `stop: yes`, or when usage has run out.

## Pipeline

Names such as batch_size come from config/run.json. XXX is the page number with 3 digits.

```
REPEAT:
  RUN run-plan.py BOOK next-batch          # prints the batch and its live pages, or "all pages are done"
  IF all pages are done: leave the loop
  SET live = the live pages it printed     # the first batch is a pilot of pilot_pages pages
  FOR try IN 1, 2:
    FOR EACH page IN live:  python shared/scripts/common.py clear-work WF_book_extraction BOOK <page>
    # (ocr-page.py only if config/ocr.json has enabled: true: RUN ocr-page.py BOOK <page> for each page)
    WAVE ext-layout-vision on every page in live           -> work/page-XXX/layout.json
    FOR EACH page IN live:  RUN crop-blocks.py BOOK <page>  -> work/page-XXX/blocks/t1.png ...
    WAVE ext-text-reader run 1 on every page in live       -> text-a.json   (brief: text-reader 1; skip if it says skip)
    FOR EACH page IN live:  RUN vote-text.py BOOK <page>   # stage 1 -> second-read.txt
    WAVE ext-text-reader run 2 on every page in live       -> text-b.json   (brief: text-reader 2; skip if it says skip)
    FOR EACH page that had run 2:  RUN vote-text.py BOOK <page>   # stage 2 -> third-read.txt
    WAVE ext-text-reader run 3 on every page in live       -> text-c.json   (brief: text-reader 3; skip if it says skip)
    FOR EACH page that had run 3:  RUN vote-text.py BOOK <page>   # stage 3 -> text-final.json, votes.json
    WAVE ext-image-bg on every page in live                -> work/page-XXX/images.json
    FOR EACH page IN live:  RUN crop-images.py BOOK <page> -> images/page_XXX_i1.jpg ...
    WAVE ext-context on every page in live                 -> work/page-XXX/context.json
    FOR EACH page IN live:
        RUN merge-page.py BOOK <page>                      -> pages/page-XXX.json
        python shared/scripts/common.py set-status WF_book_extraction BOOK <page> extracted
        RUN check-page.py BOOK <page>                      -> coverage, work/page-XXX/leftovers.json
    WAVE ext-verifier on every page in live                # replies with the report
    FOR EACH page IN live:
        check the first line (see the rules), then WRITE the reply INTO work/page-XXX/report.md
    FOR EACH page IN live:
        RUN score-page.py BOOK <page> <try>                # prints one verdict line
        verdict done or done-note:
            set-status <page> done;  RUN finish-page.py BOOK <page>;  remove the page from live
        verdict redo (only on try 1):
            RUN swap-try.py BOOK <page> save;  set-status <page> redo   # the page stays in live for try 2
        verdict done-low (only on try 2):
            RUN swap-try.py BOOK <page> keep-better;  set-status <page> done;
            RUN finish-page.py BOOK <page>;  remove the page from live
    IF live is empty: leave the try loop
  RUN build-review.py BOOK                 # rebuilt after every batch, never while pages are running
  RUN run-plan.py BOOK batch-check <first page of the batch> <last page of the batch>
  IF it prints "stop: yes": start no new batch; tell the human its sentence (the agent
     instructions probably need a fix) and that /ext-run-book BOOK resumes; stop.
```

A page whose verdict was done-note, done-low, or that has unsure blocks, doubts or unknown words has
its check note in log.csv already (score-page.py writes it); the review file shows it.

## After the run (the human's part, any time, no waiting)

Tell the human, in plain words:
- Read `BOOK_review.docx`, the "Look here first" pages first, and send corrections with
  /ext-correct BOOK <page> <what> (a word, a crop, or `again`). It edits the page JSON and rebuilds
  the review file.
- Fix every page under "A human must fix these" the same way: /ext-compile-book refuses until they
  are fixed.
- Spot-check: compare every spot_check.every_in_first-th page of the first spot_check.first_pages
  pages, then every spot_check.every_after-th page, with the original PDF. If any spot-checked page
  has mistakes, fix them, then check 1 page in 10 instead.
- Then type /ext-compile-book BOOK.
