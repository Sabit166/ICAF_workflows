"""Save or restore a try of one page with low scores. Never touches another page.

    python WF_book_extraction/scripts/swap-try.py <book_name> <page> save
    python WF_book_extraction/scripts/swap-try.py <book_name> <page> keep-better

save (before the second try): writes the page's scores from log.csv into work/page-XXX/try1/scores.json,
then moves pages/page-XXX.json, the page's crops (images/page_XXX_*) and every file in work/page-XXX/
except try1/ into work/page-XXX/try1/.

keep-better (after the second try): compares the confidence in work/page-XXX/report.md with the one in
try1/report.md. If the first try is higher, the second try's page JSON and crops are deleted, its work
files are kept in work/page-XXX/try2/, the first try's files are moved back, and its scores are written
into log.csv. Otherwise the second try stays as it is. Either way try1/ stays, so tries is 2.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402

KEEP_IN_TRY1 = {"scores.json"}


def confidence_of(report: Path) -> int:
    if not report.is_file():
        return -1
    lines = report.read_text(encoding="utf-8-sig").splitlines()
    match = re.match(r"^\s*confidence:\s*(\d{1,3})\s*$", lines[0], re.IGNORECASE) if lines else None
    return int(match.group(1)) if match else -1


def save(book, page: int) -> None:
    work = book.work(page)
    try1 = work / "try1"
    if try1.is_dir() and any(p.name not in KEEP_IN_TRY1 for p in try1.iterdir()):
        raise StopError(f"Page {page} already has a saved first try in work/{common.internal_page_name(page)}/try1/.")
    row = book.row(page)
    common.save_json(try1 / "scores.json", {k: row[k] for k in ("confidence", "coverage", "text_agreement")})
    moved = 0
    page_json = book.page_json_path(page)
    if page_json.is_file():
        common.move_path(page_json, try1 / page_json.name)
        moved += 1
    for crop in book.crops_of_page(page):
        common.move_path(crop, try1 / "images" / crop.name)
        moved += 1
    for item in list(work.iterdir()):
        if item.name != "try1":
            common.move_path(item, try1 / item.name)
            moved += 1
    print(f"swap-try: page {page}: first try saved in work/{common.internal_page_name(page)}/try1/ ({moved} items).")


def keep_better(book, page: int) -> None:
    work = book.work(page)
    try1 = work / "try1"
    if not try1.is_dir():
        raise StopError(f"Page {page} has no saved first try, so there is nothing to compare.")
    first, second = confidence_of(try1 / "report.md"), confidence_of(work / "report.md")
    if first <= second:
        print(f"swap-try: page {page}: the second try is kept (confidence {second} against {first}).")
        return
    # The first try is better: put it back.
    page_json = book.page_json_path(page)
    if page_json.is_file():
        common.remove_path(page_json)
    for crop in book.crops_of_page(page):
        common.remove_path(crop)
    try2 = work / "try2"
    if try2.exists():
        common.remove_path(try2)
    for item in list(work.iterdir()):
        if item.name not in ("try1", "try2"):
            common.move_path(item, try2 / item.name)
    saved_json = try1 / page_json.name
    if saved_json.is_file():
        common.move_path(saved_json, page_json)
    saved_images = try1 / "images"
    if saved_images.is_dir():
        for crop in list(saved_images.iterdir()):
            common.move_path(crop, book.images / crop.name)
        common.remove_path(saved_images)
    for item in list(try1.iterdir()):
        if item.name not in KEEP_IN_TRY1:
            common.move_path(item, work / item.name)
    scores_path = try1 / "scores.json"
    if scores_path.is_file():
        scores = common.read_json(scores_path)
        book.set_columns(page, **{k: scores.get(k, "") for k in ("confidence", "coverage", "text_agreement")})
    print(f"swap-try: page {page}: the first try is kept (confidence {first} against {second}).")


def main() -> None:
    book, page, rest = common.start(__file__, "required", usage="save|keep-better")
    if not rest or rest[0] not in ("save", "keep-better"):
        raise StopError("Say save or keep-better after the page number.")
    if rest[0] == "save":
        save(book, page)
    else:
        keep_better(book, page)


if __name__ == "__main__":
    common.run(main)
