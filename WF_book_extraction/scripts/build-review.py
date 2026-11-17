"""Build temp/<book_name>/<book_name>_review.docx, the one file the human checks.

    python WF_book_extraction/scripts/build-review.py <book_name>

Reads every pages/page-XXX.json in page order and log.csv. Shows all the detail (unlike the final
.md and .docx). If the file is open in Word, the new version is saved as <book_name>_review_latest.docx.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import docx_add_text as add  # noqa: E402


def context_lines(ctx: dict) -> list[str]:
    links = ", ".join(f"{l['from']} {l['relation']} {l['to']}" for l in ctx.get("links", [])) or "none"
    return [
        f"Page type: {ctx.get('page_type', '')}. Printed page number: {ctx.get('printed_page_number') or 'none'}. "
        f"Languages: {', '.join(ctx.get('languages', [])) or 'none'}.",
        f"Headings: {', '.join(ctx.get('heading_ids', [])) or 'none'}. "
        f"Running header: {', '.join(ctx.get('running_header_ids', [])) or 'none'}. "
        f"Running footer: {', '.join(ctx.get('running_footer_ids', [])) or 'none'}.",
        f"Reading flow: {', '.join(ctx.get('reading_flow', [])) or 'none'}. Links: {links}.",
        f"Layout: {ctx.get('layout_summary', '')}",
    ]


def style_line(block: dict) -> str:
    font = block["font"]
    parts = [font.get("name") or "font unknown", f"{font['size_pt']:g} pt"]
    parts.append("bold" if font["bold"] else "not bold")
    parts.append("italic" if font["italic"] else "not italic")
    parts.append(f"colour {font['color']}")
    parts.append(block["align"])
    box = ",".join(str(int(v)) for v in block["box"])
    return f"{block['id']} · {block['type']} · {block['lang']} · {block['text_status']} · box {box} · {', '.join(parts)}"


def main() -> None:
    from docx.enum.text import WD_BREAK

    book, _page, _ = common.start(__file__)
    log = book.read_log()
    total = len(log)
    done = [n for n, r in log.items() if r["status"] == "done"]
    pages = {}
    for n in sorted(log):
        path = book.page_json_path(n)
        if path.is_file():
            pages[n] = common.read_json(path)
    failed = [n for n in sorted(done) if n not in pages]
    must_fix = [n for n in sorted(log) if "needs_human" in book.tags_of(log[n])]
    look_first = [n for n in sorted(done) if log[n]["note"] and n not in failed]

    document = common.docx_new_document()
    document.add_heading(f"{book.name}: review", level=0)
    add(document, f"{len(done)} of {total} pages done", bold=True)

    document.add_heading("A human must fix these", level=1)
    if not must_fix:
        add(document, "None.")
    for n in must_fix:
        doubts = pages.get(n, {}).get("doubts", [])
        add(document, f"Page {n}: {log[n]['note'] or 'tagged needs_human'}")
        for doubt in doubts:
            add(document, f"    - {doubt}")
    add(document, "Fix each with /ext-correct <book_name> <page> <block id>: <the right text>. "
                  "/ext-compile-book refuses the book until they are fixed.", italic=True)

    document.add_heading("Look here first", level=1)
    add(document, ", ".join(str(n) for n in look_first) if look_first else "None.")

    document.add_heading("Pages that could not be processed", level=1)
    if not failed:
        add(document, "None.")
    for n in failed:
        add(document, f"Page {n}: {log[n]['note'] or common.FAILED_NOTE}")

    for n in sorted(pages):
        data = pages[n]
        row = log[n]
        document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        size = data["size"]
        document.add_heading(f"Page {n} ({size['width']} x {size['height']} px) · status {row['status']}", level=1)
        review = data.get("review")
        if review:
            add(document, f"Scores: confidence {review['confidence']}, coverage {review['coverage']}, "
                          f"text agreement {review['text_agreement']}, tries {review['tries']}, "
                          f"leftover spots {len(review['leftover_spots'])}.", bold=True)
        else:
            add(document, f"Scores so far: confidence {row['confidence'] or '-'}, coverage {row['coverage'] or '-'}, "
                          f"text agreement {row['text_agreement'] or '-'}.", bold=True)
        if row["note"]:
            add(document, f"Note: {row['note']}", color="#B00020")
        if row["tags"]:
            add(document, f"Tags: {row['tags'].replace(';', ', ')}")
        for doubt in data.get("doubts", []):
            add(document, f"Doubt: {doubt}")
        if data.get("unknown_words"):
            add(document, "Unknown words (only a hint): " + ", ".join(data["unknown_words"]))
        for block in data["text_blocks"]:
            if block["text_status"] in ("voted", "unsure"):
                add(document, f"{block['id']} is {block['text_status']}: {block['text']}")
                for other in block["other_readings"]:
                    add(document, f"    {other['reader']}: {other['text']}")
        if review:
            add(document, f"Checker notes: {review['checker_notes']}", italic=True)

        document.add_heading("Background", level=2)
        bg = data["background"]
        add(document, f"Colour {bg['color']}. {bg['description']}")
        add(document, f"Rebuild notes: {bg['rebuild_notes'] or 'none'}. Boxes: {len(bg['boxes'])}.")

        document.add_heading("Context", level=2)
        for line in context_lines(data["context"]):
            add(document, line)

        document.add_heading("Text blocks", level=2)
        for block in data["text_blocks"]:
            font = block["font"]
            add(document, block["text"], bold=font["bold"], italic=font["italic"], size_pt=font["size_pt"],
                color=font["color"], align=block["align"])
            add(document, style_line(block), size_pt=8, color="#666666")

        document.add_heading("Image blocks", level=2)
        if not data["images"]:
            add(document, "None.")
        for image in data["images"]:
            box = ",".join(str(int(v)) for v in image["box"])
            add(document, f"{image['id']} · {image['kind']} · {image['file']}", bold=True)
            add(document, f"Box {box}. Layer {image['layer']}, rotation {image['rotation_deg']}°, opacity {image['opacity']}. "
                          f"Overlaps text: {', '.join(image['overlaps_text']) or 'none'}.")
            add(document, f"Summary: {image['summary']}")
            add(document, f"Description: {image['description']}")
            add(document, f"Purpose: {image['purpose']}. Style: {image['style']}. "
                          f"Main colours: {', '.join(image['main_colors']) or 'none'}.")
            add(document, f"Rebuild notes: {image['rebuild_notes'] or 'none'}")

    target = book.review_path
    try:
        written = common.docx_save(document, target)
        extra = ""
    except PermissionError:
        written = common.docx_save(document, target.with_name(f"{book.name}_review_latest.docx"))
        extra = f" {target.name} is open in Word, so the new version was saved as {written.name}."
    print(f"build-review: {written.relative_to(common.ROOT).as_posix()} built: {len(done)} of {total} pages done, "
          f"{len(must_fix)} need a human, {len(look_first)} to look at first.{extra}")


if __name__ == "__main__":
    common.run(main)
