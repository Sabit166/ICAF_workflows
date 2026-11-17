"""Copy a compiled book to output/ (or, for a sample, to samples/), check it, then delete its temp folder.

    python WF_book_extraction/scripts/finalize-book.py <book_name>

Only /ext-compile-book runs it, after the count check. Never replaces or deletes anything in output/.

A normal book goes to output/<book_name>/ if that does not exist yet, otherwise to the next free
output/<book_name>_copy_N/, whose three book files are named <book_name>_copy_N.json, .md and .docx.
It copies (never moves) the book files, log.csv, renders/ and images/, checks every file arrived with
the same size, and only then deletes temp/<book_name>/. If anything fails, it deletes the half-made
target folder (nothing else), leaves temp/ as it is, and stops with one plain sentence.

A sample book (sample_...) never goes to output/. The first time it is saved as the sample answer in
samples/<wf>/output/<book_name>/; later it is compared with that answer and the differences are printed.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402


def copy_book(book, target: Path, file_stem: str) -> list[tuple[Path, Path]]:
    """Copy the kept files into target; returns (source, copy) pairs."""
    pairs = [(book.book_json_path, target / f"{file_stem}.json"),
             (book.book_md_path, target / f"{file_stem}.md"),
             (book.book_docx_path, target / f"{file_stem}.docx"),
             (book.log_path, target / "log.csv")]
    for folder in (book.renders, book.images):
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path.is_file() and ".tmp-" not in path.name:
                    pairs.append((path, target / folder.name / path.name))
    target.mkdir(parents=True, exist_ok=False)
    (target / "renders").mkdir(exist_ok=True)
    (target / "images").mkdir(exist_ok=True)
    for source, copy in pairs:
        shutil.copy2(source, copy)
    for source, copy in pairs:
        if not copy.is_file() or copy.stat().st_size != source.stat().st_size:
            raise OSError(f"{copy.name} did not arrive whole")
    return pairs


def next_target(book) -> tuple[Path, str]:
    base = book.output_root / book.name
    if not base.exists():
        return base, book.name
    n = 1
    while (book.output_root / f"{book.name}_copy_{n}").exists():
        n += 1
    name = f"{book.name}_copy_{n}"
    return book.output_root / name, name


def compare_with_sample(new: dict, old: dict) -> list[str]:
    diffs = []
    if new.get("page_count") != old.get("page_count"):
        diffs.append(f"The page count is {new.get('page_count')} now and {old.get('page_count')} in the sample answer.")
    old_pages = {p["page"]: p for p in old.get("pages", [])}
    for page in new.get("pages", []):
        n = page["page"]
        before = old_pages.get(n)
        if before is None:
            diffs.append(f"Page {n} is not in the sample answer.")
            continue
        if bool(page.get("failed")) != bool(before.get("failed")):
            diffs.append(f"Page {n} {'could not be processed now' if page.get('failed') else 'was not processed in the sample answer'}.")
            continue
        if page.get("failed"):
            continue
        old_text = {b["id"]: b["text"] for b in before.get("text_blocks", [])}
        new_text = {b["id"]: b["text"] for b in page.get("text_blocks", [])}
        for block_id in sorted(set(old_text) | set(new_text), key=lambda x: int(x[1:])):
            if block_id not in new_text:
                diffs.append(f"Page {n}: text block {block_id} is missing now.")
            elif block_id not in old_text:
                diffs.append(f"Page {n}: text block {block_id} is new.")
            elif old_text[block_id] != new_text[block_id]:
                diffs.append(f"Page {n}: {block_id} reads \"{new_text[block_id]}\" now and \"{old_text[block_id]}\" in the sample answer.")
        old_kinds = sorted(i["kind"] for i in before.get("images", []))
        new_kinds = sorted(i["kind"] for i in page.get("images", []))
        if old_kinds != new_kinds:
            diffs.append(f"Page {n}: image blocks are {', '.join(new_kinds) or 'none'} now and "
                         f"{', '.join(old_kinds) or 'none'} in the sample answer.")
    return diffs


def main() -> None:
    book, _page, _ = common.start(__file__)
    for path in (book.book_json_path, book.book_md_path, book.book_docx_path, book.log_path):
        if not path.is_file():
            raise StopError(f"{path.name} is missing. Run the compile steps first (/ext-compile-book {book.name}).")

    if book.is_sample:
        answer = common.samples_output(book.wf) / book.name
        if not answer.exists():
            try:
                copy_book(book, answer, book.name)
            except Exception as err:
                common.remove_path(answer)
                raise StopError(f"The sample answer could not be saved ({err}). temp/{book.name}/ is kept; run again.")
            common.remove_path(book.temp)
            print(f"Saved as the sample answer in {answer.relative_to(common.ROOT).as_posix()}/. "
                  "Check it by hand before you commit it.")
            return
        saved = answer / f"{book.name}.json"
        if not saved.is_file():
            raise StopError(f"{saved.relative_to(common.ROOT).as_posix()} is missing, so the sample cannot be compared.")
        diffs = compare_with_sample(common.read_json(book.book_json_path), common.read_json(saved))
        print("\n".join(diffs) if diffs else "No differences.")
        common.remove_path(book.temp)
        print(f"temp/{book.name}/ deleted. Nothing was written to samples/.")
        return

    target, stem = next_target(book)
    try:
        pairs = copy_book(book, target, stem)
    except Exception as err:
        if target.exists():
            common.remove_path(target)
        raise StopError(f"The book could not be copied to output/ ({err}). temp/{book.name}/ is kept; run again.")
    common.remove_path(book.temp)
    copy_note = f" This is copy {stem.rsplit('_', 1)[-1]} (the earlier versions are untouched)." if stem != book.name else ""
    print(f"finalize-book: {len(pairs)} files copied to {target.relative_to(common.ROOT).as_posix()}/ and checked; "
          f"temp/{book.name}/ deleted.{copy_note}")


if __name__ == "__main__":
    common.run(main)
