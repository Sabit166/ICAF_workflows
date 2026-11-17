"""Read the PDF's own hidden text layer, word by word, into pdf-words.json (written once).

    python WF_book_extraction/scripts/check-text-layer.py <book_name> [page]

If pdf-words.json exists already, it does nothing. Word boxes are scaled to the page renders.
Bijoy/ANSI text is converted with common.bijoy_to_unicode() and never discarded; a page whose text
still looks wrong is marked "doubt": true. A page with no usable text layer gets the tag
no_text_layer and no entry.
"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


def _bad_char(ch: str) -> bool:
    code = ord(ch)
    return ch == "�" or 0xE000 <= code <= 0xF8FF or (code < 32 and ch not in "\t\n\r")


def _span_is_bijoy(span: dict) -> bool:
    if common.is_bijoy_font(span.get("font", "")):
        return True
    text = "".join(c["c"] for c in span.get("chars", []))
    if common.has_bengali(text):
        return False
    symbols = common.bijoy_symbols()
    has_latin = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in text)
    return has_latin and any(ch in symbols for ch in text)


def extract_words(pdf_page, scale: float):
    """Words with boxes in pixels of the render. Returns (words, readable)."""
    import pymupdf

    raw = pdf_page.get_text("rawdict")
    rotation = pdf_page.rotation_matrix if pdf_page.rotation else None
    words = []
    all_chars = 0
    bad_chars = 0

    def flush(current):
        if not current["chars"]:
            return
        text = "".join(ch for ch, _ in current["chars"])
        rect = pymupdf.Rect(current["chars"][0][1])
        for _, bbox in current["chars"][1:]:
            rect |= pymupdf.Rect(bbox)
        if rotation is not None:
            rect = rect * rotation
        box = [round(rect.x0 * scale, 1), round(rect.y0 * scale, 1), round(rect.x1 * scale, 1), round(rect.y1 * scale, 1)]
        words.append({"raw": text, "box": box, "bijoy": current["bijoy"]})

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            current = {"chars": [], "bijoy": False}
            for span in line.get("spans", []):
                span_bijoy = _span_is_bijoy(span)
                for char in span.get("chars", []):
                    ch = char["c"]
                    if not ch.isspace():
                        all_chars += 1
                        bad_chars += _bad_char(ch)
                    if ch.isspace():
                        flush(current)
                        current = {"chars": [], "bijoy": False}
                        continue
                    current["chars"].append((ch, char["bbox"]))
                    current["bijoy"] = current["bijoy"] or span_bijoy
            flush(current)
    readable = all_chars > 0 and bad_chars / all_chars < 0.3
    return words, readable


def clean_words(words):
    """Convert, check and clean the words of one page. Returns (words, bijoy, doubt)."""
    out = []
    page_bijoy = False
    doubt = False
    for word in words:
        raw = unicodedata.normalize("NFC", word["raw"])
        raw = "".join(ch for ch in raw if not _bad_char(ch))
        if not raw.strip():
            continue
        entry = {"box": word["box"]}
        if common.has_bengali(raw):
            text = raw
            if not common.looks_like_unicode_bangla(text):
                doubt = True
        elif word["bijoy"]:
            text = common.bijoy_to_unicode(raw, force=True)
            entry["bijoy"] = True
            page_bijoy = True
            if common.leftover_symbols(text) or (common.has_bengali(text) and not common.looks_like_unicode_bangla(text)):
                doubt = True
        else:
            text = raw
        text = common.clean_text(text)
        if text:
            entry["text"] = text
            out.append({"text": entry["text"], "box": entry["box"], **({"bijoy": True} if entry.get("bijoy") else {})})
    return out, page_bijoy, doubt


def main() -> None:
    import pymupdf

    book, _page, _ = common.start(__file__, "optional")
    if book.pdf_words_path.is_file():
        print("check-text-layer: pdf-words.json exists already; nothing to do.")
        return
    info = book.book_info_all()
    pdf_path = book.pdf_path
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception:
        raise StopError(f"The PDF {pdf_path.name} cannot be opened. It may be damaged or locked with a password. "
                        "Replace it and run again.")
    pages_out = {}
    no_layer = bijoy_pages = doubt_pages = 0
    for n in range(1, doc.page_count + 1):
        entry = info["pages"].get(common.output_page_name(n))
        if entry is None:
            continue
        try:
            raw_words, readable = extract_words(doc[n - 1], entry["scale"])
        except Exception:
            raw_words, readable = [], False
        words, bijoy, doubt = clean_words(raw_words) if readable else ([], False, False)
        if not words:
            no_layer += 1
            book.add_tag(n, "no_text_layer")
            continue
        book.remove_tag(n, "no_text_layer")
        bijoy_pages += bijoy
        doubt_pages += doubt
        pages_out[common.output_page_name(n)] = {"words": words, "bijoy": bijoy, "doubt": doubt}
    common.save_json(book.pdf_words_path, {"pages": pages_out})
    print(f"check-text-layer: {len(pages_out)} pages have PDF text ({bijoy_pages} converted from Bijoy, "
          f"{doubt_pages} marked doubt); {no_layer} pages have no usable text layer.")


if __name__ == "__main__":
    common.run(main)
