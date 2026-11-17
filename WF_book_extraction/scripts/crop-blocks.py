"""Cut every text block of one page out of the ORIGINAL PDF page, for the ext-text-reader.

    python WF_book_extraction/scripts/crop-blocks.py <book_name> <page>

Reads work/page-XXX/layout.json (boxes in pixels of the render). Draws the PDF page at
block_crop.dpi and saves work/page-XXX/blocks/t1.png, t2.png ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402

MAX_PIXELS = 80_000_000


def draw_page(book, page: int, dpi: int):
    """The page drawn at dpi as a PIL image (rotation as in the render)."""
    import pymupdf
    from PIL import Image

    doc = pymupdf.open(str(book.pdf_path))
    pdf_page = doc[page - 1]
    zoom = dpi / 72.0
    pixels = pdf_page.rect.width * zoom * pdf_page.rect.height * zoom
    if pixels > MAX_PIXELS:
        zoom *= (MAX_PIXELS / pixels) ** 0.5
    pix = pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return image, zoom / pdf_page_scale(book, page)


def pdf_page_scale(book, page: int) -> float:
    return float(book.book_info(page)["scale"])


def main() -> None:
    import io

    book, page, _ = common.start(__file__, "required")
    work = book.work(page)
    layout_path = work / "layout.json"
    if not layout_path.is_file():
        book.fail(page, f"layout.json of page {page} is missing, so its text blocks cannot be cut out.")
    blocks = common.read_json(layout_path).get("text_blocks", [])
    if not blocks:
        print(f"crop-blocks: page {page} has no text blocks; no crops made.")
        return
    entry = book.book_info(page)
    width, height = entry["width"], entry["height"]
    cfg = book.config("render")["block_crop"]
    image, factor = draw_page(book, page, cfg["dpi"])
    out_dir = work / "blocks"
    if out_dir.is_dir():
        for old in out_dir.glob("t*.png"):
            common.remove_path(old)
    out_dir.mkdir(parents=True, exist_ok=True)
    pad = cfg["padding_px"]
    made, skipped = 0, []
    for block in blocks:
        box = common.clip_box(block["box"], width, height)
        if box is None:
            skipped.append(block["id"])
            continue
        left, top = max(0, box[0] - pad), max(0, box[1] - pad)
        right, bottom = min(width, box[2] + pad), min(height, box[3] + pad)
        crop = image.crop((int(left * factor), int(top * factor),
                           min(image.width, int(right * factor + 0.999)), min(image.height, int(bottom * factor + 0.999))))
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG", optimize=True)
        common.write_bytes_atomic(out_dir / f"{block['id']}.png", buffer.getvalue())
        made += 1
    if skipped:
        book.add_note(page, f"Text blocks {', '.join(skipped)} have no area on the page and were skipped.")
    print(f"crop-blocks: page {page}: {made} block crops made, {len(skipped)} skipped.")


if __name__ == "__main__":
    common.run(main)
