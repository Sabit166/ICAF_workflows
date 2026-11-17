---
name: ext-fix-book
description: Reopens a compiled book of WF_book_extraction so that a mistake can be fixed.
argument-hint: <book_name>
disable-model-invocation: true
---

# /ext-fix-book $ARGUMENTS

BOOK is the book name given as the argument. Every command is one plain command with the Bash tool.

1. Run `python shared/scripts/check-root.py`. If it does not print ok, stop and tell the human its
   sentence.
2. The argument is a book name. Stop if `WF_book_extraction/output/BOOK/` is missing (there is no
   finished book of that name), or if `WF_book_extraction/temp/BOOK/` already exists (a run or a fix
   is already open: finish it with /ext-compile-book BOOK first).
3. Tell the human what happens, and ask them to confirm before going on:
   - the finished output stays untouched;
   - the newest version of the book (`output/BOOK/` or its highest `_copy_N`) is reopened in
     `temp/BOOK/`;
   - compiling it again makes a new copy, and nothing in output/ is replaced.
4. Run `python WF_book_extraction/scripts/reopen-book.py BOOK`.
5. Tell the human to send corrections with /ext-correct BOOK <page> <what>, to read the rebuilt
   review file `WF_book_extraction/temp/BOOK/BOOK_review.docx`, and then to type
   /ext-compile-book BOOK when they are happy.
