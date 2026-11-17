"""Build temp/<book_name>/<book_name>.docx from <book_name>.json (not from the .md).

    python WF_book_extraction/scripts/make-docx.py <book_name>

Same content as the .md, with each text block styled as saved (font, size, bold, italic, colour,
alignment), a Bangla font, and each page on a new page. Crops are not embedded: their file names
are shown. No scores, no check notes. After writing, it reads the file back and checks that every
text and image block id of every page appears exactly once.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402
from common import docx_add_text as add  # noqa: E402

PAGE_TITLE = re.compile(r"^Page (\d+)$")
BLOCK_TITLE = re.compile(r"^([ti]\d+) · ")


def none(values) -> str:
    return ", ".join(values) if values else "none"


def box_text(box) -> str:
    return ",".join(str(int(v)) for v in box)


def style_text(block: dict) -> str:
    font = block["font"]
    parts = [font.get("name") or "font unknown", f"{font['size_pt']:g} pt"]
    if font["bold"]:
        parts.append("bold")
    if font["italic"]:
        parts.append("italic")
    parts.append(f"colour {font['color']}")
    parts.append(block["align"])
    return ", ".join(parts)


def build(data: dict):
    from docx.enum.text import WD_BREAK

    document = common.docx_new_document()
    document.add_heading(data["book"], level=0)
    for index, page in enumerate(data["pages"]):
        if index:
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        document.add_heading(f"Page {page['page']}", level=1)
        if page.get("failed"):
            add(document, common.FAILED_NOTE)
            continue
        bg = page["background"]
        ctx = page["context"]
        links = ", ".join(f"{l['from']} {l['relation']} {l['to']}" for l in ctx["links"]) or "none"
        add(document, f"Background: colour {bg['color']}. {bg['summary']}")
        add(document, "Context:", bold=True)
        add(document, f"Page type: {ctx['page_type']}. Printed page number: {ctx['printed_page_number'] or 'none'}. "
                      f"Languages: {none(ctx['languages'])}.")
        add(document, f"Headings: {none(ctx['heading_ids'])}. Running header: {none(ctx['running_header_ids'])}. "
                      f"Running footer: {none(ctx['running_footer_ids'])}.")
        add(document, f"Reading flow: {none(ctx['reading_flow'])}. Links: {links}.")
        add(document, f"Layout: {ctx['layout_summary']}")
        for block in sorted(page["text_blocks"], key=lambda b: b["order"]):
            document.add_heading(f"{block['id']} · {block['type']}", level=3)
            font = block["font"]
            add(document, block["text"], font_name=font.get("name"), size_pt=font["size_pt"], bold=font["bold"],
                italic=font["italic"], color=font["color"], align=block["align"])
            add(document, f"Style: {style_text(block)}. Box: {box_text(block['box'])}.", size_pt=8, color="#666666")
        for image in page["images"]:
            document.add_heading(f"{image['id']} · {image['kind']} · {image['file']}", level=3)
            add(document, f"Box: {box_text(image['box'])}. Purpose: {image['purpose']}")
            add(document, f"Summary: {image['summary']}")
    return document


def check_ids(path: Path, data: dict) -> list[str]:
    from docx import Document

    document = Document(str(path))
    found: dict[int, list[str]] = {}
    failed_seen: dict[int, int] = {}
    current = None
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        match = PAGE_TITLE.match(text) if paragraph.style.name.startswith("Heading") else None
        if match:
            current = int(match.group(1))
            found.setdefault(current, [])
            continue
        if current is None:
            continue
        if paragraph.style.name.startswith("Heading"):
            block = BLOCK_TITLE.match(text)
            if block:
                found[current].append(block.group(1))
        elif text == common.FAILED_NOTE:
            failed_seen[current] = failed_seen.get(current, 0) + 1
    problems = []
    for page in data["pages"]:
        n = page["page"]
        if n not in found:
            problems.append(f"page {n} is missing")
            continue
        if page.get("failed"):
            if failed_seen.get(n, 0) != 1:
                problems.append(f"page {n}: the failed-page note is missing")
            continue
        for block_id in [b["id"] for b in page["text_blocks"]] + [i["id"] for i in page["images"]]:
            count = found[n].count(block_id)
            if count != 1:
                problems.append(f"page {n}: {block_id} appears {count} times")
    return problems


def main() -> None:
    book, _page, _ = common.start(__file__)
    if not book.book_json_path.is_file():
        raise StopError(f"{book.book_json_path.name} is missing. Run merge-book.py {book.name} first.")
    data = common.read_json(book.book_json_path)
    document = build(data)
    try:
        common.docx_save(document, book.book_docx_path)
    except PermissionError:
        raise StopError(f"{book.book_docx_path.name} is open in Word. Close it, then run again.")
    problems = check_ids(book.book_docx_path, data)
    if problems:
        raise StopError(f"{book.book_docx_path.name} is missing blocks: " + "; ".join(problems[:10]))
    blocks = sum(len(p.get("text_blocks", [])) for p in data["pages"])
    images = sum(len(p.get("images", [])) for p in data["pages"])
    failed = sum(1 for p in data["pages"] if p.get("failed"))
    print(f"make-docx: ok: {book.book_docx_path.name} written; {blocks} text blocks, {images} image blocks and "
          f"{failed} failed pages each appear exactly once.")


if __name__ == "__main__":
    common.run(main)
