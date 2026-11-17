"""Add the review section to a page JSON when the page is done. Deletes nothing.

    python WF_book_extraction/scripts/finish-page.py <book_name> <page>

Reads the first line of work/page-XXX/report.md (confidence: N), the verifier's notes after it,
leftovers.json, coverage and text_agreement from log.csv, and whether work/page-XXX/try1/ exists.
If the page still has the tag latin_text, it adds the tag needs_human.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402

CONFIDENCE_LINE = re.compile(r"^\s*confidence:\s*(\d{1,3})\s*$", re.IGNORECASE)


def read_report(path: Path):
    """(confidence, notes) from a report.md, or None if the first line is not 'confidence: N'."""
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return None
    match = CONFIDENCE_LINE.match(lines[0])
    if not match or not 0 <= int(match.group(1)) <= 100:
        return None
    return int(match.group(1)), "\n".join(lines[1:]).strip()


def main() -> None:
    book, page, _ = common.start(__file__, "required")
    work = book.work(page)
    page_path = book.page_json_path(page)
    if not page_path.is_file():
        book.fail(page, f"pages/{common.internal_page_name(page)}.json is missing, so the page cannot be finished.")
    report = read_report(work / "report.md")
    if report is None:
        book.fail(page, "The first line of report.md is not 'confidence: <0-100>', so the page cannot be finished.")
    confidence, notes = report
    leftovers_path = work / "leftovers.json"
    spots = common.read_json(leftovers_path).get("spots", []) if leftovers_path.is_file() else []
    row = book.row(page)
    try:
        coverage = float(row["coverage"])
        text_agreement = float(row["text_agreement"])
    except ValueError:
        book.fail(page, "log.csv has no coverage or text_agreement for this page, so it cannot be finished.")
    data = common.read_json(page_path)
    data["review"] = {
        "confidence": confidence,
        "coverage": round(min(1.0, max(0.0, coverage)), 4),
        "text_agreement": round(min(1.0, max(0.0, text_agreement)), 4),
        "tries": 2 if (work / "try1").is_dir() else 1,
        "leftover_spots": spots,
        "checker_notes": notes or "No notes.",
    }
    try:
        common.save_json(page_path, data)
    except StopError as err:
        book.fail(page, f"The review could not be added: {err}")
    book.set_columns(page, confidence=confidence)
    if book.has_tag(page, "latin_text"):
        book.add_tag(page, "needs_human")
    print(f"finish-page: page {page}: review added (confidence {confidence}, coverage {coverage}, "
          f"text_agreement {text_agreement}, tries {data['review']['tries']}).")


if __name__ == "__main__":
    common.run(main)
