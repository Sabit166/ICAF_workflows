---
name: ext-compile-book
description: Finishes a book of WF_book_extraction - merges the pages, builds the .md and .docx and moves the book to output/.
argument-hint: <book_name>
disable-model-invocation: true
---

# /ext-compile-book $ARGUMENTS

BOOK is the book name given as the argument. RUN x.py means one plain command with the Bash tool:
`python WF_book_extraction/scripts/x.py BOOK`. No variable in front, no && or ;.

1. Run `python shared/scripts/check-root.py`. If it does not print ok, stop and tell the human its
   sentence.
2. The argument is a book name. Stop if `WF_book_extraction/temp/BOOK/` is missing (say: a finished
   book is reopened with /ext-fix-book BOOK; a new book is run with /ext-run-book BOOK).
3. RUN `run-plan.py BOOK status`. If any page is listed under needs_human, stop and name those pages:
   a human fixes them with /ext-correct first. If any page is not done, stop and name the pages. A
   page that is done but has no page JSON (it could not be processed) is allowed: it goes in the
   book as an empty page with the note "This page could not be processed."
4. For a book that is not a sample: if `WF_book_extraction/output/BOOK/` already exists, the result
   becomes a new copy (finalize-book.py picks the next free `BOOK_copy_N`). Nothing in output/ is
   ever replaced or deleted. Say so to the human.
5. RUN merge-book.py: it writes `BOOK.json` in temp/BOOK/.
6. RUN make-md.py and RUN make-docx.py: both build their file from the JSON.
7. Count check: make-md.py and make-docx.py each read their file back and print
   `ok: ... each appear exactly once` when every text block id and image block id of every page,
   and every failed page with its note, appears exactly once. If either did not print ok, stop and
   name what it said is missing.
8. RUN finalize-book.py. It copies the finished files into `output/BOOK/`, or into the next free
   `output/BOOK_copy_N/`, checks them, and only then deletes the book's temp folder. For a sample
   book it saves to, or compares with, `samples/WF_book_extraction/output/BOOK/` instead of output/.
9. Tell the human what finalize-book.py printed: where the files are, and the copy number if it made
   a new copy, or the sample comparison. Say that the result can now be committed in git (the human
   commits; Claude never does).
