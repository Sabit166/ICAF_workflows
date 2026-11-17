"""Decide what happens to a page after the verifier, from the limits in config/run.json.

    python WF_book_extraction/scripts/score-page.py <book_name> <page> <try>

Reads the confidence from work/page-XXX/report.md (and writes it into log.csv), coverage and
text_agreement from log.csv, the tag latin_text, and the page JSON (unsure blocks, unknown words,
doubts). Prints one verdict line, which the main session follows:

  verdict: done        all three scores good, nothing to check
  verdict: done-note   done, with a check note (written into log.csv by this script)
  verdict: redo        low score or latin_text on try 1: run swap-try.py save, then the page again
  verdict: done-low    low score or latin_text on try 2: run swap-try.py keep-better, then done
                       (the note "Low scores after 2 tries. Read this page carefully." is written)

Check reasons are also saved as tags check_<reason>, so run-plan.py batch-check can count them.
It changes no status: the main session does that with common.py set-status.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402

CONFIDENCE_LINE = re.compile(r"^\s*confidence:\s*(\d{1,3})\s*$", re.IGNORECASE)
LOW_NOTE = "Low scores after 2 tries. Read this page carefully."
CHECK_PREFIX = "Check this page:"
REASON_TAGS = ["check_middle_confidence", "check_middle_coverage", "check_middle_text_agreement",
               "check_unsure_blocks", "check_doubts", "check_unknown_words", "check_low_after_2_tries"]


def band(value: float, limits: dict) -> str:
    if value >= limits["good"]:
        return "good"
    if value >= limits["low"]:
        return "middle"
    return "low"


def main() -> None:
    book, page, rest = common.start(__file__, "required", usage="<try>")
    try_number = int(rest[0]) if rest and rest[0].isdigit() else 1
    work = book.work(page)
    report = work / "report.md"
    first = report.read_text(encoding="utf-8-sig").splitlines()[:1] if report.is_file() else []
    match = CONFIDENCE_LINE.match(first[0]) if first else None
    confidence = int(match.group(1)) if match and int(match.group(1)) <= 100 else 0
    book.set_columns(page, confidence=confidence)
    row = book.row(page)

    def number(key):
        try:
            return float(row[key])
        except ValueError:
            return 0.0

    scores = {"confidence": confidence, "coverage": number("coverage"), "text_agreement": number("text_agreement")}
    limits = book.config("run")["scores"]
    bands = {key: band(value, limits[key]) for key, value in scores.items()}
    latin = "latin_text" in book.tags_of(row)

    for tag in REASON_TAGS:
        if tag in book.tags_of(row):
            book.remove_tag(page, tag)
    book.remove_note_part(page, CHECK_PREFIX)
    book.remove_note_part(page, LOW_NOTE)

    if "low" in bands.values() or latin:
        why = [f"{k} {scores[k]} is low" for k, b in bands.items() if b == "low"]
        if latin:
            why.append("Bengali text is still in Latin letters")
        if try_number < 2:
            print("verdict: redo")
            print("why: " + "; ".join(why))
            return
        book.add_note(page, LOW_NOTE)
        book.add_tag(page, "check_low_after_2_tries")
        print("verdict: done-low")
        print("why: " + "; ".join(why))
        return

    reasons, tags = [], []
    for key in ("confidence", "coverage", "text_agreement"):
        if bands[key] == "middle":
            reasons.append(f"{key.replace('_', ' ')} {scores[key]} is in the middle band")
            tags.append(f"check_middle_{key}")
    page_path = book.page_json_path(page)
    data = common.read_json(page_path) if page_path.is_file() else {}
    unsure = [b["id"] for b in data.get("text_blocks", []) if b.get("text_status") == "unsure"]
    if unsure:
        reasons.append(f"blocks {', '.join(unsure)} are unsure")
        tags.append("check_unsure_blocks")
    if data.get("doubts"):
        reasons.append(f"{len(data['doubts'])} doubts")
        tags.append("check_doubts")
    if data.get("unknown_words"):
        reasons.append(f"{len(data['unknown_words'])} unknown words")
        tags.append("check_unknown_words")
    if not reasons:
        print("verdict: done")
        return
    for tag in tags:
        book.add_tag(page, tag)
    book.add_note(page, f"{CHECK_PREFIX} {'; '.join(reasons)}.")
    print("verdict: done-note")
    print("why: " + "; ".join(reasons))


if __name__ == "__main__":
    common.run(main)
