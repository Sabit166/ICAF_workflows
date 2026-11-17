"""Optional: Google Cloud Vision OCR of one page into work/page-XXX/ocr.json.

    python WF_book_extraction/scripts/ocr-page.py <book_name> <page>

Runs only if config/ocr.json has enabled: true. Draws the page at the dpi in ocr.json, sends it to
Google Cloud Vision with the language hints, and saves every word with its box (scaled to the render)
and confidence. vote-text.py then uses ocr.json as one more reader.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


def main() -> None:
    book, page, _ = common.start(__file__, "required")
    cfg = book.config("ocr")
    if not cfg.get("enabled"):
        print("ocr-page: Google OCR is off (config/ocr.json enabled: false); nothing to do.")
        return
    if cfg.get("engine") != "google_vision":
        raise StopError(f"The OCR engine {cfg.get('engine')} is not supported. Use google_vision.")
    try:
        from google.cloud import vision
    except ImportError:
        raise StopError("The package google-cloud-vision is missing. Run: pip install google-cloud-vision")
    import pymupdf

    doc = pymupdf.open(str(book.pdf_path))
    zoom = cfg.get("dpi", 300) / 72.0
    pix = doc[page - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    factor = float(book.book_info(page)["scale"]) / zoom
    client = vision.ImageAnnotatorClient()
    response = client.document_text_detection(
        image=vision.Image(content=pix.tobytes("png")),
        image_context={"language_hints": cfg.get("language_hints", ["bn", "en"])})
    if response.error.message:
        book.fail(page, f"Google OCR failed on page {page}: {response.error.message}")
    words = []
    for page_part in response.full_text_annotation.pages:
        for block in page_part.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    text = "".join(symbol.text for symbol in word.symbols)
                    xs = [v.x for v in word.bounding_box.vertices]
                    ys = [v.y for v in word.bounding_box.vertices]
                    words.append({"text": common.clean_text(text),
                                  "box": [round(min(xs) * factor, 1), round(min(ys) * factor, 1),
                                          round(max(xs) * factor, 1), round(max(ys) * factor, 1)],
                                  "confidence": round(float(word.confidence), 4)})
    common.save_json(book.work(page) / "ocr.json", {"words": words})
    print(f"ocr-page: page {page}: {len(words)} words saved to ocr.json.")


if __name__ == "__main__":
    common.run(main)
