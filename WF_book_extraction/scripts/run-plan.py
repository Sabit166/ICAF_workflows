"""Plain answers for the main session while it runs a book. Reads files; changes nothing.

    python WF_book_extraction/scripts/run-plan.py <book_name> status
    python WF_book_extraction/scripts/run-plan.py <book_name> next-batch
    python WF_book_extraction/scripts/run-plan.py <book_name> brief <page> <agent> [run]
    python WF_book_extraction/scripts/run-plan.py <book_name> batch-check <first_page> <last_page>

status       counts of pages per status, and the pages that need attention.
next-batch   the first batch (pilot_pages, then batch_size pages each) that still has pages not done,
             and its live pages.
brief        the exact text to give one agent run for one page: the page number, the full paths it may
             open and the one file it must write. Prints "skip: <why>" when the run is not needed.
             agent is one of: layout-vision, text-reader, image-bg, context, verifier.
             For text-reader, run is 1, 2 or 3.
batch-check  counts the check notes of the batch by reason (from the check_<reason> tags that
             score-page.py writes) and prints "stop: no" or "stop: yes ..." (stop_after_same_note).
             Unknown words and doubts are noted on the page but not counted here: the word list is
             only a hint, so they come up on most pages.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402

COUNTED_REASONS = ["check_middle_confidence", "check_middle_coverage", "check_middle_text_agreement",
                   "check_unsure_blocks", "check_low_after_2_tries"]
READER_FILES = {"1": "text-a.json", "2": "text-b.json", "3": "text-c.json"}


def p(path: Path) -> str:
    return path.resolve().as_posix()


def batches(book) -> list[list[int]]:
    cfg = book.config("run")
    pages = sorted(book.read_log())
    pilot, size = int(cfg["pilot_pages"]), int(cfg["batch_size"])
    out = [pages[:pilot]] if pilot else []
    rest = pages[pilot:]
    out += [rest[i:i + size] for i in range(0, len(rest), size)]
    return [b for b in out if b]


def status(book) -> None:
    log = book.read_log()
    counts = {s: 0 for s in common.STATUSES}
    for row in log.values():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"{book.name}: {len(log)} pages; " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    render_failed = [n for n, r in sorted(log.items()) if "render_failed" in book.tags_of(r) and r["status"] != "done"]
    needs_human = [n for n, r in sorted(log.items()) if "needs_human" in book.tags_of(r)]
    print("render_failed and not done yet: " + (" ".join(map(str, render_failed)) or "none"))
    print("needs_human: " + (" ".join(map(str, needs_human)) or "none"))


def next_batch(book) -> None:
    log = book.read_log()
    all_batches = batches(book)
    for index, batch in enumerate(all_batches, start=1):
        live = [n for n in batch if log[n]["status"] != "done"]
        if live:
            kind = "pilot " if index == 1 and len(all_batches) > 1 and book.config("run")["pilot_pages"] else ""
            print(f"{kind}batch {index} of {len(all_batches)}: pages {batch[0]}-{batch[-1]}")
            print("live: " + " ".join(map(str, live)))
            return
    print("all pages are done")


def brief(book, page: int, agent: str, run: str | None) -> None:
    work = book.work(page)
    render = book.render_path(page)
    try:
        entry = book.book_info(page)
    except StopError:
        print(f"skip: page {page} has no render")
        return
    size = f"{entry['width']} x {entry['height']} px"
    head = f"Book {book.name}, page {page}. The page render is {size}; all boxes are pixels of this render."
    layout_path = work / "layout.json"

    if agent == "layout-vision":
        print(head)
        print("Open only:")
        print(f"- {p(render)}")
        print("Write only:")
        print(f"- {p(layout_path)}")
        return

    if agent == "image-bg":
        print(head)
        print("Open only:")
        print(f"- {p(render)}")
        print("Write only:")
        print(f"- {p(work / 'images.json')}")
        return

    if agent == "context":
        print(head)
        print("Open only:")
        for path in (render, layout_path, work / "images.json"):
            print(f"- {p(path)}")
        print("Write only:")
        print(f"- {p(work / 'context.json')}")
        return

    if agent == "text-reader":
        if run not in READER_FILES:
            raise StopError("Say the reading run (1, 2 or 3) after text-reader.")
        if not layout_path.is_file():
            print("skip: layout.json is missing")
            return
        ids = [b["id"] for b in sorted(common.read_json(layout_path).get("text_blocks", []), key=lambda b: b["order"])]
        if run == "2":
            listed = work / "second-read.txt"
            ids = [i for i in listed.read_text(encoding="utf-8").split() if i] if listed.is_file() else []
        elif run == "3":
            listed = work / "third-read.txt"
            ids = [i for i in listed.read_text(encoding="utf-8").split() if i] if listed.is_file() else []
        if not ids:
            print(f"skip: no text blocks to read in run {run}")
            return
        crops = [work / "blocks" / f"{i}.png" for i in ids]
        missing = [c.name for c in crops if not c.is_file()]
        if missing:
            print(f"skip: block crops are missing ({', '.join(missing)}); run crop-blocks.py {book.name} {page} first")
            return
        print(f"Page {page}, reading run {run}. Read each crop and type exactly what is printed.")
        print("Open only these block crops:")
        for crop in crops:
            print(f"- {p(crop)}")
        print("Write only:")
        print(f"- {p(work / READER_FILES[run])}")
        print(f"with exactly these keys: {', '.join(ids)}")
        return

    if agent == "verifier":
        page_json = book.page_json_path(page)
        if not page_json.is_file():
            print("skip: the page JSON is missing")
            return
        print(head)
        print("You write no file: reply with the report. Open only:")
        paths = [page_json, render] + book.crops_of_page(page)
        paths += [work / "context.json", work / "votes.json", work / "leftovers.json"]
        blocks_dir = work / "blocks"
        for path in paths:
            if path.is_file():
                print(f"- {p(path)}")
        if blocks_dir.is_dir():
            print("Only if a word is too small to read on the render, also open its block crop:")
            for crop in sorted(blocks_dir.glob("t*.png"), key=lambda c: int(c.stem[1:])):
                print(f"- {p(crop)}")
        return

    raise StopError(f"{agent} is not an agent of this workflow. Use layout-vision, text-reader, image-bg, context or verifier.")


def batch_check(book, first: int, last: int) -> None:
    log = book.read_log()
    limit = int(book.config("run")["stop_after_same_note"])
    counts = {}
    for n in range(first, last + 1):
        row = log.get(n)
        if row is None:
            continue
        for tag in book.tags_of(row):
            if tag in COUNTED_REASONS:
                counts.setdefault(tag, []).append(n)
    worst = max(counts.items(), key=lambda kv: len(kv[1]), default=None)
    for tag, pages in sorted(counts.items()):
        print(f"{tag}: pages {' '.join(map(str, pages))}")
    if worst and len(worst[1]) >= limit:
        reason = worst[0].replace("check_", "").replace("_", " ")
        print(f"stop: yes. {len(worst[1])} pages in this batch got the same check note ({reason}). "
              "The agent instructions probably need a fix.")
    else:
        print("stop: no")


def main() -> None:
    book, _page, rest = common.start(__file__, usage="status|next-batch|brief|batch-check")
    if not rest:
        raise StopError("Say status, next-batch, brief or batch-check after the book name.")
    command = rest[0]
    if command == "status":
        status(book)
    elif command == "next-batch":
        next_batch(book)
    elif command == "brief":
        if len(rest) < 3 or not rest[1].isdigit():
            raise StopError("Use: run-plan.py <book_name> brief <page> <agent> [run]")
        brief(book, int(rest[1]), rest[2], rest[3] if len(rest) > 3 else None)
    elif command == "batch-check":
        if len(rest) < 3 or not (rest[1].isdigit() and rest[2].isdigit()):
            raise StopError("Use: run-plan.py <book_name> batch-check <first_page> <last_page>")
        batch_check(book, int(rest[1]), int(rest[2]))
    else:
        raise StopError(f"Unknown command {command}. Use status, next-batch, brief or batch-check.")


if __name__ == "__main__":
    common.run(main)
