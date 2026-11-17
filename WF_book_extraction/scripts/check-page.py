"""Two plain-maths checks of one page, no AI: coverage and Latin letters in Bengali text.

    python WF_book_extraction/scripts/check-page.py <book_name> <page>

Coverage: paint over every text box, image box and background box of the page JSON on the render,
and count the ink that is left. Coverage = ink inside boxes / all ink (1.0 for an empty page).
Leftover ink spots go to work/page-XXX/leftovers.json. Coverage goes to log.csv.
Latin check: a Bengali block whose letters are 80% or more Latin gets the tag latin_text.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402

INK_DISTANCE = 60      # a pixel is ink when a colour channel differs this much from the background
BOX_MARGIN = 3         # px painted around every box
CELL = 16              # px; leftover ink is grouped in cells of this size
MIN_CELL_INK = 6       # ink pixels for a cell to count
MIN_SPOT_INK = 40      # ink pixels for a leftover spot to be reported
LATIN_LIMIT = 0.8
LATIN_NOTE = "Bengali text is still in Latin letters (Bijoy not converted)."


def background_color(pixels):
    import numpy as np
    quantized = (pixels // 16).reshape(-1, 3)
    keys = quantized[:, 0].astype(np.int32) * 256 + quantized[:, 1].astype(np.int32) * 16 + quantized[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    top = values[np.argmax(counts)]
    mask = keys == top
    return pixels.reshape(-1, 3)[mask].mean(axis=0)


def leftover_spots(outside):
    """Group leftover ink into boxes (cells joined with their 8 neighbours)."""
    import numpy as np
    height, width = outside.shape
    rows, cols = (height + CELL - 1) // CELL, (width + CELL - 1) // CELL
    padded = np.zeros((rows * CELL, cols * CELL), dtype=bool)
    padded[:height, :width] = outside
    cell_ink = padded.reshape(rows, CELL, cols, CELL).sum(axis=(1, 3))
    marked = cell_ink >= MIN_CELL_INK
    seen = np.zeros_like(marked)
    spots = []
    for r in range(rows):
        for c in range(cols):
            if not marked[r, c] or seen[r, c]:
                continue
            stack, cells = [(r, c)], []
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < rows and 0 <= nx < cols and marked[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ink = int(sum(cell_ink[y, x] for y, x in cells))
            if ink < MIN_SPOT_INK:
                continue
            ys, xs = [y for y, _ in cells], [x for _, x in cells]
            spots.append([min(xs) * CELL, min(ys) * CELL, min(width, (max(xs) + 1) * CELL), min(height, (max(ys) + 1) * CELL)])
    return spots


def main() -> None:
    import numpy as np
    from PIL import Image

    book, page, _ = common.start(__file__, "required")
    page_path = book.page_json_path(page)
    if not page_path.is_file():
        book.fail(page, f"pages/{common.internal_page_name(page)}.json is missing, so the page cannot be checked.")
    data = common.read_json(page_path)
    render = book.render_path(page)
    if not render.is_file():
        book.fail(page, f"The render of page {page} is missing, so the page cannot be checked.")

    with Image.open(render) as image:
        pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
    height, width = pixels.shape[:2]
    bg = background_color(pixels)
    ink = np.abs(pixels - bg).max(axis=2) > INK_DISTANCE
    covered = np.zeros((height, width), dtype=bool)
    boxes = [b["box"] for b in data["text_blocks"]] + [i["box"] for i in data["images"]] + data["background"]["boxes"]
    for box in boxes:
        clipped = common.clip_box(box, width, height)
        if clipped is None:
            continue
        l, t, r, b = clipped
        covered[max(0, t - BOX_MARGIN):min(height, b + BOX_MARGIN), max(0, l - BOX_MARGIN):min(width, r + BOX_MARGIN)] = True
    total = int(ink.sum())
    inside = int((ink & covered).sum())
    coverage = 1.0 if total == 0 else inside / total
    spots = leftover_spots(ink & ~covered) if total else []
    common.save_json(book.work(page) / "leftovers.json", {"spots": spots})
    book.set_columns(page, coverage=f"{coverage:.4f}")

    pdf_entry = book.pdf_words(page)
    bijoy_blocks = set()
    if pdf_entry:
        assigned = common.assign_words(pdf_entry["words"], data["text_blocks"])
        bijoy_blocks = {bid for bid, words in assigned.items() if any(w.get("bijoy") for w in words)}
    latin = [b["id"] for b in data["text_blocks"]
             if (b["lang"] == "bn" or b["id"] in bijoy_blocks) and common.latin_share(b["text"]) >= LATIN_LIMIT]
    book.remove_note_part(page, LATIN_NOTE)
    if latin:
        book.add_tag(page, "latin_text")
        for block_id in latin:
            book.add_note(page, f"{block_id}: {LATIN_NOTE}")
    else:
        book.remove_tag(page, "latin_text")
    print(f"check-page: page {page}: coverage {coverage:.4f}, {len(spots)} leftover spots, "
          f"{len(latin)} Bengali blocks still in Latin letters.")


if __name__ == "__main__":
    common.run(main)
