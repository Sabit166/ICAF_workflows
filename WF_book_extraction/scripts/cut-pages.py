"""Render every page of a book as a JPEG and write book-info.json once.

    python WF_book_extraction/scripts/cut-pages.py <book_name> [page]

Without a page number, only pages that have no render yet are drawn (so a stopped book resumes).
With a page number, that page is drawn again even if its render exists.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


def open_pdf(pdf_path: Path):
    import pymupdf
    sentence = (f"The PDF {pdf_path.name} cannot be opened. It may be damaged or locked with a password. "
                "Replace it and run again.")
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception:
        raise StopError(sentence)
    if doc.needs_pass or doc.page_count == 0:
        raise StopError(sentence)
    return doc


def jpeg_bytes(image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def render_page(pdf_page, out_path: Path, cfg: dict):
    """Draw one page at about long_side_px; lower the quality, then the size, until it is under max_kb.
    Returns (entry, too_big)."""
    import pymupdf
    from PIL import Image

    max_bytes = cfg["max_kb"] * 1024
    rect = pdf_page.rect
    longest = max(rect.width, rect.height)
    side = cfg["long_side_px"]
    best = None
    quality = cfg["jpeg_quality"]
    while True:
        zoom = side / longest
        pix = pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        while True:
            data = jpeg_bytes(image, quality)
            if best is None or len(data) < len(best[0]):
                best = (data, image.size)
            if len(data) <= max_bytes:
                return _save(out_path, data, image.size, rect), False
            if quality - 5 >= cfg["min_jpeg_quality"]:
                quality -= 5
                continue
            quality = cfg["min_jpeg_quality"]
            break
        if side - 50 >= cfg["min_long_side_px"]:
            side -= 50
            continue
        break
    data, size = best
    return _save(out_path, data, size, rect), True


def _save(out_path: Path, data: bytes, size, rect) -> dict:
    common.write_bytes_atomic(out_path, data)
    width, height = size
    return {"width": width, "height": height, "scale": round(width / rect.width, 6),
            "file_size_kb": round(len(data) / 1024, 1)}


def main() -> None:
    from PIL import Image

    book, page, _ = common.start(__file__, "optional")
    pdf_path = book.pdf_path
    doc = open_pdf(pdf_path)
    fingerprint = common.pdf_fingerprint(pdf_path)
    if book.book_info_path.is_file():
        saved = common.read_json(book.book_info_path).get("pdf_sha256")
        if saved != fingerprint:
            raise StopError(f"{pdf_path.name} has changed since this book was started. Put the old PDF back, "
                            f"or delete temp/{book.name}/ by hand to start again.")
    if page is not None and page > doc.page_count:
        raise StopError(f"{book.name} has only {doc.page_count} pages.")

    book.renders.mkdir(parents=True, exist_ok=True)
    book.ensure_log(doc.page_count)
    cfg = book.config("render")["page_render"]
    pages = [page] if page is not None else range(1, doc.page_count + 1)
    rendered = too_big = failed = 0
    for n in pages:
        out_path = book.render_path(n)
        if page is None and out_path.is_file():
            continue
        try:
            _entry, big = render_page(doc[n - 1], out_path, cfg)
        except Exception:
            failed += 1
            book.add_tag(n, "render_failed")
            continue
        rendered += 1
        book.remove_tag(n, "render_failed")
        if big:
            too_big += 1
            book.add_tag(n, "over_500kb")
        else:
            book.remove_tag(n, "over_500kb")

    if not book.book_info_path.is_file():
        entries = {}
        for n in range(1, doc.page_count + 1):
            out_path = book.render_path(n)
            if not out_path.is_file():
                continue
            with Image.open(out_path) as image:
                width, height = image.size
            entries[common.output_page_name(n)] = {
                "width": width, "height": height, "scale": round(width / doc[n - 1].rect.width, 6),
                "file_size_kb": round(out_path.stat().st_size / 1024, 1)}
        common.save_json(book.book_info_path, {"pages": entries, "pdf_sha256": fingerprint})

    not_drawn = sum(1 for n in range(1, doc.page_count + 1) if not book.render_path(n).is_file())
    print(f"cut-pages: {book.name} has {doc.page_count} pages; rendered {rendered} now, "
          f"{too_big} too big (kept smallest), {not_drawn} could not be drawn.")


if __name__ == "__main__":
    common.run(main)
