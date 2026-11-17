"""Merge every page JSON of a book into temp/<book_name>/<book_name>.json.

    python WF_book_extraction/scripts/merge-book.py <book_name>

A page with no page JSON (it could not be processed) is added in the short form
{"page": 7, "failed": true, "note": "This page could not be processed."}.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402


def main() -> None:
    book, _page, _ = common.start(__file__)
    log = book.read_log()
    pages, failed = [], 0
    for n in sorted(log):
        path = book.page_json_path(n)
        if path.is_file():
            pages.append(common.read_json(path))
        else:
            pages.append({"page": n, "failed": True, "note": common.FAILED_NOTE})
            failed += 1
    try:
        source = book.pdf_path.name
    except common.StopError:
        source = f"{book.name}.pdf"
    data = {"book": book.name, "source_pdf": source, "page_count": len(log), "pages": pages}
    common.save_json(book.book_json_path, data)
    print(f"merge-book: {book.book_json_path.relative_to(common.ROOT).as_posix()} written: "
          f"{len(log)} pages, {failed} could not be processed.")


if __name__ == "__main__":
    common.run(main)
