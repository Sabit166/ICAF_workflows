---
name: ext-correct
description: Fixes one page of a WF_book_extraction book - a wrong word, a wrong crop, or running the page again.
argument-hint: <book_name> <page> <what>
disable-model-invocation: true
---

# /ext-correct $ARGUMENTS

The arguments are BOOK (the book name), PAGE (the page number) and WHAT, one of:
- `<block id>: <the right text>` (for example `t3: আমার`): a wrong word;
- `crop <image id>` (for example `crop i1`): a wrong crop;
- `again`: run the page again.

XXX is PAGE with 3 digits. Every command is one plain command with the Bash tool: no variable in
front, no && or ;.

1. Run `python shared/scripts/check-root.py`. If it does not print ok, stop and tell the human its
   sentence.
2. If `WF_book_extraction/temp/BOOK/` is missing because the book is already compiled, stop and say:
   "Type /ext-fix-book BOOK first."
3. A wrong word: open `WF_book_extraction/temp/BOOK/pages/page-XXX.json` with Read, and with Edit
   replace the `text` of that block with the text the human gave, exactly as given (never change a
   letter of it; Unicode NFC). Add "<block id>: Corrected by the human." to the page's `doubts`, and
   remove that block's "<block id>: unconverted symbol in ..." doubts. The check-schema.py hook checks
   the file as it is saved: fix any problem it reports. If no block of the page is still flagged (no
   "unconverted symbol" doubt left, and no block still mostly in Latin letters), run
   `python shared/scripts/common.py remove-tag WF_book_extraction BOOK PAGE needs_human`
   and `python shared/scripts/common.py remove-tag WF_book_extraction BOOK PAGE latin_text`.
   Then run `python WF_book_extraction/scripts/build-review.py BOOK`.
4. A wrong crop: look at the page render (`WF_book_extraction/temp/BOOK/renders/page_XXX.jpg`) and
   the crop (`WF_book_extraction/temp/BOOK/images/page_XXX_<image id>.jpg` or `.png`). Fix the `box`
   of that image block in the page JSON with Edit (pixels of the render, [left, top, right, bottom]).
   Then run `python WF_book_extraction/scripts/crop-images.py BOOK PAGE`, then
   `python WF_book_extraction/scripts/build-review.py BOOK`. If it is not clear what is wrong, ask the
   human first.
5. Run again: run `python shared/scripts/common.py set-status WF_book_extraction BOOK PAGE new`, then
   tell the human to type /ext-run-book BOOK.
6. Tell the human what changed.
