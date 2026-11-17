"""Cut every image block of one page out of the ORIGINAL PDF page into temp/<book_name>/images/.

    python WF_book_extraction/scripts/crop-images.py <book_name> <page>

Reads work/page-XXX/images.json, or pages/page-XXX.json when images.json is missing (so a wrong
box fixed in the page JSON can be cropped again). Photo-like kinds are saved as JPEG, line-art
kinds as PNG. Files are named page_XXX_<id>.jpg or .png.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402

MAX_PIXELS = 80_000_000


def draw_page(book, page: int, dpi: int):
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
    return image, zoom / float(book.book_info(page)["scale"])


def encode(image, ext: str, quality: int) -> bytes:
    buffer = io.BytesIO()
    if ext == "jpg":
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
    else:
        image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def fit_size(image, ext: str, cfg: dict):
    """Lower the quality (JPEG), then the size, until under max_kb. Returns (bytes, too_big)."""
    from PIL import Image

    max_bytes = cfg["max_kb"] * 1024
    quality = cfg["jpeg_quality"]
    current = image
    best = None
    while True:
        while True:
            data = encode(current, ext, quality)
            if best is None or len(data) < len(best):
                best = data
            if len(data) <= max_bytes:
                return data, False
            if ext == "jpg" and quality - 5 >= cfg["min_jpeg_quality"]:
                quality -= 5
                continue
            break
        long_side = max(current.size)
        new_long = int(long_side * 0.9)
        if new_long < cfg["min_long_side_px"]:
            return best, True
        shrink = new_long / max(image.size)
        current = image.resize((max(1, int(image.width * shrink)), max(1, int(image.height * shrink))), Image.LANCZOS)


def main() -> None:
    book, page, _ = common.start(__file__, "required")
    work = book.work(page)
    images_path = work / "images.json"
    if images_path.is_file():
        blocks = common.read_json(images_path).get("images", [])
    elif book.page_json_path(page).is_file():
        blocks = common.read_json(book.page_json_path(page)).get("images", [])
    else:
        book.fail(page, f"images.json of page {page} is missing, so its image blocks cannot be cut out.")
    if not blocks:
        print(f"crop-images: page {page} has no image blocks; no crops made.")
        return
    entry = book.book_info(page)
    width, height = entry["width"], entry["height"]
    cfg = book.config("render")["image_crop"]
    image, factor = draw_page(book, page, cfg["dpi"])
    book.images.mkdir(parents=True, exist_ok=True)
    pad = cfg["padding_px"]
    made, skipped, too_big = 0, [], 0
    for block in blocks:
        box = common.clip_box(block["box"], width, height)
        if box is None:
            skipped.append(block["id"])
            continue
        left, top = max(0, box[0] - pad), max(0, box[1] - pad)
        right, bottom = min(width, box[2] + pad), min(height, box[3] + pad)
        crop = image.crop((int(left * factor), int(top * factor),
                           min(image.width, int(right * factor + 0.999)), min(image.height, int(bottom * factor + 0.999))))
        ext = "jpg" if block.get("kind") in cfg["jpeg_kinds"] else "png"
        data, big = fit_size(crop, ext, cfg)
        target = book.crop_path(page, block["id"], ext)
        other = book.crop_path(page, block["id"], "png" if ext == "jpg" else "jpg")
        common.write_bytes_atomic(target, data)
        if other.is_file():
            common.remove_path(other)
        made += 1
        too_big += big
    if too_big:
        book.add_tag(page, "image_over_1mb")
    else:
        book.remove_tag(page, "image_over_1mb")
    if skipped:
        book.add_note(page, f"Image blocks {', '.join(skipped)} have no area on the page and were skipped.")
    print(f"crop-images: page {page}: {made} crops made ({too_big} over the size limit), {len(skipped)} skipped.")


if __name__ == "__main__":
    common.run(main)
