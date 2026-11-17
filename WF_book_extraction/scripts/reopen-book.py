"""Reopen a compiled book into temp/<book_name>/ so a mistake can be fixed.

    python WF_book_extraction/scripts/reopen-book.py <book_name>

Takes the newest version: the highest output/<book_name>_copy_N/, or output/<book_name>/. Copies (never
moves) images/, renders/ and log.csv; splits the book JSON into pages/page-XXX.json; rebuilds
book-info.json from the renders and pdf-words.json (as check-text-layer.py does); tags every page
reopened; builds the review file. Never touches output/ and deletes nothing.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


def newest_version(book) -> tuple[Path, str]:
    base = book.output_root / book.name
    if not base.is_dir():
        raise StopError(f"output/{book.name}/ is missing, so there is no finished book to reopen.")
    best, best_n = base, 0
    for folder in book.output_root.iterdir():
        match = re.fullmatch(rf"{re.escape(book.name)}_copy_(\d+)", folder.name)
        if match and folder.is_dir() and int(match.group(1)) > best_n:
            best, best_n = folder, int(match.group(1))
    return best, best.name


def main() -> None:
    import pymupdf
    from PIL import Image

    book, _page, _ = common.start(__file__)
    source, stem = newest_version(book)
    if book.temp.exists():
        raise StopError(f"temp/{book.name}/ already exists: a run or a fix is already open.")
    book_json = source / f"{stem}.json"
    if not book_json.is_file():
        book_json = source / f"{book.name}.json"
    if not book_json.is_file():
        raise StopError(f"{source.name}/ has no book JSON, so it cannot be reopened.")
    pdf_path = book.pdf_path
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception:
        raise StopError(f"The PDF {pdf_path.name} cannot be opened. It may be damaged or locked with a password. "
                        "Replace it and run again.")

    book.temp.mkdir(parents=True)
    for folder in ("renders", "images"):
        if (source / folder).is_dir():
            shutil.copytree(source / folder, book.temp / folder)
        else:
            (book.temp / folder).mkdir()
    shutil.copy2(source / "log.csv", book.log_path)

    data = common.read_json(book_json)
    split = 0
    for page in data["pages"]:
        if page.get("failed"):
            continue
        common.save_json(book.page_json_path(page["page"]), page)
        split += 1

    entries = {}
    for n in range(1, doc.page_count + 1):
        render = book.render_path(n)
        if not render.is_file():
            continue
        with Image.open(render) as image:
            width, height = image.size
        entries[common.output_page_name(n)] = {"width": width, "height": height,
                                               "scale": round(width / doc[n - 1].rect.width, 6),
                                               "file_size_kb": round(render.stat().st_size / 1024, 1)}
    common.save_json(book.book_info_path, {"pages": entries, "pdf_sha256": common.pdf_fingerprint(pdf_path)})

    scripts = Path(__file__).resolve().parent
    result = subprocess.run([sys.executable, str(scripts / "check-text-layer.py"), book.name],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise StopError(f"pdf-words.json could not be rebuilt: {result.stdout.strip() or result.stderr.strip()}")
    for n in book.read_log():
        book.add_tag(n, "reopened")
    result = subprocess.run([sys.executable, str(scripts / "build-review.py"), book.name],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    review = result.stdout.strip() or result.stderr.strip()
    print(f"reopen-book: {source.name}/ reopened into temp/{book.name}/ ({split} page JSON files). "
          f"output/ was not touched. {review}")


if __name__ == "__main__":
    common.run(main)
