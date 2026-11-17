"""Build temp/<book_name>/<book_name>.md from <book_name>.json.

    python WF_book_extraction/scripts/make-md.py <book_name>

For each page: page number, background colour and summary, the full context, every text block in
reading order exactly as saved (with type, box and style), and every image block (id, kind, crop
file, box, purpose, summary). No scores, no check notes. After writing, it reads the file back and
checks that every text and image block id of every page appears exactly once.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


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


def page_md(page: dict) -> list[str]:
    lines = [f"## Page {page['page']}", ""]
    if page.get("failed"):
        return lines + [common.FAILED_NOTE, ""]
    bg = page["background"]
    ctx = page["context"]
    links = ", ".join(f"{l['from']} {l['relation']} {l['to']}" for l in ctx["links"]) or "none"
    lines += [
        f"Background: colour {bg['color']}. {bg['summary']}",
        "",
        "Context:",
        f"- Page type: {ctx['page_type']}. Printed page number: {ctx['printed_page_number'] or 'none'}. "
        f"Languages: {none(ctx['languages'])}.",
        f"- Headings: {none(ctx['heading_ids'])}. Running header: {none(ctx['running_header_ids'])}. "
        f"Running footer: {none(ctx['running_footer_ids'])}.",
        f"- Reading flow: {none(ctx['reading_flow'])}. Links: {links}.",
        f"- Layout: {ctx['layout_summary']}",
        "",
    ]
    for block in sorted(page["text_blocks"], key=lambda b: b["order"]):
        lines += [f"### {block['id']} · {block['type']}", "", block["text"], "",
                  f"Style: {style_text(block)}. Box: {box_text(block['box'])}.", ""]
    for image in page["images"]:
        lines += [f"### {image['id']} · {image['kind']} · {image['file']}", "",
                  f"Box: {box_text(image['box'])}. Purpose: {image['purpose']}",
                  "", f"Summary: {image['summary']}", ""]
    return lines


def check_ids(md_text: str, data: dict) -> list[str]:
    """Every block id appears exactly once as a block heading of its page; every failed page once."""
    problems = []
    sections = re.split(r"(?m)^## Page (\d+)\s*$", md_text)
    found = {}
    for i in range(1, len(sections), 2):
        found.setdefault(int(sections[i]), []).append(sections[i + 1])
    for page in data["pages"]:
        n = page["page"]
        bodies = found.get(n, [])
        if len(bodies) != 1:
            problems.append(f"page {n} appears {len(bodies)} times")
            continue
        body = bodies[0]
        if page.get("failed"):
            if body.count(common.FAILED_NOTE) != 1:
                problems.append(f"page {n}: the failed-page note is missing")
            continue
        ids = [b["id"] for b in page["text_blocks"]] + [i["id"] for i in page["images"]]
        for block_id in ids:
            count = len(re.findall(rf"(?m)^### {re.escape(block_id)} · ", body))
            if count != 1:
                problems.append(f"page {n}: {block_id} appears {count} times")
    return problems


def main() -> None:
    book, _page, _ = common.start(__file__)
    if not book.book_json_path.is_file():
        raise StopError(f"{book.book_json_path.name} is missing. Run merge-book.py {book.name} first.")
    data = common.read_json(book.book_json_path)
    lines = [f"# {data['book']}", ""]
    for page in data["pages"]:
        lines += page_md(page)
    text = "\n".join(lines).rstrip() + "\n"
    common.write_text_atomic(book.book_md_path, text)
    problems = check_ids(book.book_md_path.read_text(encoding="utf-8"), data)
    if problems:
        raise StopError(f"{book.book_md_path.name} is missing blocks: " + "; ".join(problems[:10]))
    blocks = sum(len(p.get("text_blocks", [])) for p in data["pages"])
    images = sum(len(p.get("images", [])) for p in data["pages"])
    failed = sum(1 for p in data["pages"] if p.get("failed"))
    print(f"make-md: ok: {book.book_md_path.name} written; {blocks} text blocks, {images} image blocks and "
          f"{failed} failed pages each appear exactly once.")


if __name__ == "__main__":
    common.run(main)
