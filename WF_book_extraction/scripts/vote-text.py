"""Vote on the text of every text block of one page.

    python WF_book_extraction/scripts/vote-text.py <book_name> <page>

The stage comes from the files in work/page-XXX/:
  stage 1: only text-a.json        -> second-read.txt (blocks that need a second Claude reading)
  stage 2: text-b.json as well     -> third-read.txt (blocks still unresolved), text_agreement
  stage 3: text-c.json as well     -> word-by-word vote
When nothing is left to read, it writes text-final.json and votes.json.
Readers: text_a, text_b, text_c (Claude), pdf (the PDF's own text) and ocr (only if ocr.json exists).
"""
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import compare_form  # noqa: E402

MISSING = "[?]"


def read_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ids(path: Path, ids: list[str]) -> None:
    common.write_text_atomic(path, "".join(f"{i}\n" for i in ids))


def english_text_ok(text: str) -> bool:
    letters = [ch for ch in text if ch.isalnum()]
    return bool(letters) and not common.has_bengali(text) and not any(ch in common.bijoy_symbols() for ch in text)


class Block:
    def __init__(self, layout_block: dict, pdf_words: list, ocr_words: list):
        self.id = layout_block["id"]
        self.pdf_bijoy = any(w.get("bijoy") for w in pdf_words)
        self.lang = "bn" if (layout_block.get("lang") == "bn" or self.pdf_bijoy) else layout_block.get("lang", "bn")
        self.pdf_text = common.clean_text(common.words_in_reading_order(pdf_words))
        self.ocr_text = common.clean_text(common.words_in_reading_order(ocr_words)) if ocr_words else None
        if not self.pdf_text:
            self.pdf_usable = False
        elif self.pdf_bijoy:
            self.pdf_usable = True
        elif self.lang == "bn":
            self.pdf_usable = common.looks_like_unicode_bangla(self.pdf_text)
        else:
            self.pdf_usable = english_text_ok(self.pdf_text)
        self.bijoy_converted = False

    def reader_text(self, answers: dict | None) -> str:
        """A reader's text for this block: cleaned, Bijoy converted for a Bengali block."""
        if answers is None or self.id not in answers or not isinstance(answers[self.id], str):
            return MISSING
        text = answers[self.id]
        if self.lang == "bn" and common.is_bijoy_latin(text):
            text = common.bijoy_to_unicode(text, force=True)
            self.bijoy_converted = True
        return common.clean_text(text)


def word_vote(readers: list[tuple[str, str]]) -> tuple[str, bool]:
    """Vote word by word, aligned to text_a. Returns (text, all_resolved)."""
    a_text = readers[0][1]
    tokens = re.split(r"(\s+)", a_text)
    a_words = tokens[0::2]
    seps = tokens[1::2]
    keep = [i for i, w in enumerate(a_words) if w]
    a_words = [a_words[i] for i in keep]
    seps = [" "] + [seps[i - 1] if 0 < i <= len(seps) else " " for i in keep[1:]]
    n = len(a_words)
    positions = [{readers[0][0]: a_words[i]} for i in range(n)]
    gaps = [dict() for _ in range(n + 1)]
    for name, text in readers[1:]:
        r_words = compare_form(text).split()
        matcher = SequenceMatcher(None, [compare_form(w) for w in a_words], r_words, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
                for k in range(i2 - i1):
                    positions[i1 + k][name] = r_words[j1 + k]
            elif tag == "replace":
                positions[i1][name] = " ".join(r_words[j1:j2])
                for k in range(i1 + 1, i2):
                    positions[k][name] = ""
            elif tag == "delete":
                for k in range(i1, i2):
                    positions[k][name] = ""
            elif tag == "insert":
                gaps[i1][name] = " ".join(r_words[j1:j2])
    names = [name for name, _ in readers]
    resolved = True
    out_words: list[tuple[str, str]] = []

    def decide(candidates: dict, fallback: str, is_gap: bool):
        nonlocal resolved
        counts = Counter(compare_form(candidates.get(name, "")) for name in names)
        ranked = counts.most_common()
        top_value, top_count = ranked[0]
        unique = len(ranked) == 1 or ranked[1][1] < top_count
        if top_count >= 2 and unique:
            if compare_form(fallback) == top_value:
                return fallback
            return top_value
        resolved = False
        if is_gap:
            return MISSING
        return f"{MISSING}{fallback}"

    for i in range(n + 1):
        if gaps[i]:
            word = decide(gaps[i], "", True)
            if word:
                out_words.append((" ", word))
        if i < n:
            word = decide(positions[i], a_words[i], False)
            if word:
                out_words.append((seps[i], word))
    text = ""
    for index, (sep, word) in enumerate(out_words):
        text += ("" if index == 0 else (sep if sep else " ")) + word
    return text, resolved


def whole_vote(readers: list[tuple[str, str]]):
    """If one whole text has at least 2 readers and more than any other, return it."""
    counts = Counter(compare_form(t) for _, t in readers)
    ranked = counts.most_common()
    top_value, top_count = ranked[0]
    if top_count >= 2 and (len(ranked) == 1 or ranked[1][1] < top_count) and top_value != compare_form(MISSING):
        for _, text in readers:
            if compare_form(text) == top_value:
                return text
    return None


def losers(readers: list[tuple[str, str]], final: str, skip: tuple = ()) -> list[dict]:
    target = compare_form(final)
    return [{"reader": name, "text": text} for name, text in readers
            if name not in skip and compare_form(text) != target]


def main() -> None:
    book, page, _ = common.start(__file__, "required")
    work = book.work(page)
    layout_path = work / "layout.json"
    if not layout_path.is_file():
        book.fail(page, f"layout.json of page {page} is missing, so its text cannot be voted.")
    layout_blocks = sorted(common.read_json(layout_path).get("text_blocks", []), key=lambda b: b.get("order", 0))
    final_path, votes_path = work / "text-final.json", work / "votes.json"
    second_path, third_path = work / "second-read.txt", work / "third-read.txt"

    if not layout_blocks:
        common.save_json(final_path, {})
        common.save_json(votes_path, {"blocks": {}, "unknown_words": [], "doubts": [], "needs_human": []})
        write_ids(second_path, [])
        book.set_columns(page, text_agreement="1.0")
        print(f"vote-text: page {page} has no text blocks; text_agreement 1.0.")
        return

    def load(name):
        path = work / name
        return common.read_json(path) if path.is_file() else None

    text_a = load("text-a.json")
    if text_a is None:
        book.fail(page, f"text-a.json of page {page} is missing, so its text cannot be voted.")
    text_b, text_c = load("text-b.json"), load("text-c.json")
    stage = 3 if text_c is not None else (2 if text_b is not None else 1)
    if stage == 3 and text_b is None:
        book.fail(page, f"text-c.json of page {page} exists without text-b.json.")

    pdf_entry = book.pdf_words(page)
    pdf_by_block = common.assign_words(pdf_entry["words"] if pdf_entry else [], layout_blocks)
    ocr_data = load("ocr.json")
    ocr_by_block = common.assign_words(ocr_data["words"], layout_blocks) if ocr_data else {}
    blocks = [Block(b, pdf_by_block[b["id"]], ocr_by_block.get(b["id"], [])) for b in layout_blocks]

    a = {b.id: b.reader_text(text_a) for b in blocks}
    b_text = {b.id: b.reader_text(text_b) for b in blocks} if text_b is not None else {}
    c_text = {b.id: b.reader_text(text_c) for b in blocks} if text_c is not None else {}

    final: dict[str, str] = {}
    status: dict[str, str] = {}
    others: dict[str, list] = {}

    # Stage 1: text-a against the PDF's own text.
    second = []
    for blk in blocks:
        if blk.pdf_usable and compare_form(a[blk.id]) == compare_form(blk.pdf_text):
            final[blk.id], status[blk.id], others[blk.id] = a[blk.id], "agreed", []
        else:
            second.append(blk.id)
    if stage == 1:
        write_ids(second_path, second)
        if second:
            print(f"vote-text: page {page} stage 1: {len(blocks) - len(second)} blocks agreed with the PDF text; "
                  f"{len(second)} need a second reading (second-read.txt).")
            return

    # Stage 2: text-b for the blocks in second-read.txt.
    third = []
    if stage >= 2:
        for blk in blocks:
            if blk.id not in second:
                continue
            ra, rb = a[blk.id], b_text.get(blk.id, MISSING)
            if blk.pdf_usable:
                if compare_form(ra) == compare_form(rb) and ra != MISSING:
                    final[blk.id], status[blk.id] = ra, "voted"
                    others[blk.id] = [{"reader": "pdf", "text": blk.pdf_text}]
                elif compare_form(rb) == compare_form(blk.pdf_text) and rb != MISSING:
                    final[blk.id], status[blk.id] = rb, "voted"
                    others[blk.id] = [{"reader": "text_a", "text": ra}]
                else:
                    third.append(blk.id)
            elif compare_form(ra) == compare_form(rb) and ra != MISSING:
                final[blk.id], status[blk.id], others[blk.id] = ra, "agreed", []
            else:
                third.append(blk.id)
        if stage == 2:
            write_ids(third_path, third)

    # Scores of the first comparison (text-a against the PDF text, or against text-b).
    read_agreement = {}
    differing = total = 0
    for blk in blocks:
        partner = blk.pdf_text if blk.pdf_usable else b_text.get(blk.id, MISSING if stage >= 2 else a[blk.id])
        x, y = compare_form(a[blk.id]), compare_form(partner)
        d, t = common.char_diff(x, y)
        differing, total = differing + d, total + t
        read_agreement[blk.id] = common.word_agreement(x, y)
    text_agreement = round(1 - differing / total, 4) if total else 1.0
    book.set_columns(page, text_agreement=f"{text_agreement}")

    if stage == 2 and third:
        print(f"vote-text: page {page} stage 2: {len(third)} blocks still unresolved (third-read.txt); "
              f"text_agreement {text_agreement}.")
        return

    # Stage 3: every reader, word by word.
    if stage == 3:
        for block_id in read_ids(third_path) or third:
            blk = next((x for x in blocks if x.id == block_id), None)
            if blk is None:
                continue
            readers = [("text_a", a[blk.id]), ("text_b", b_text.get(blk.id, MISSING)), ("text_c", c_text.get(blk.id, MISSING))]
            if blk.pdf_usable:
                readers.append(("pdf", blk.pdf_text))
                if blk.ocr_text:
                    readers.append(("ocr", blk.ocr_text))
            elif blk.ocr_text:
                readers.append(("ocr", blk.ocr_text))
            winner = whole_vote(readers)
            if winner is not None:
                final[blk.id], status[blk.id] = winner, "voted"
                others[blk.id] = losers(readers, winner)
                continue
            text, resolved = word_vote(readers)
            final[blk.id] = text
            if resolved:
                status[blk.id], others[blk.id] = "voted", losers(readers, text)
            else:
                status[blk.id], others[blk.id] = "unsure", losers(readers, text, skip=("text_a",))

    # Anything not decided (a stage was skipped) keeps text-a, marked unsure.
    for blk in blocks:
        if blk.id not in final:
            final[blk.id] = a[blk.id] if a[blk.id].startswith(MISSING) else f"{MISSING}{a[blk.id]}"
            status[blk.id], others[blk.id] = "unsure", []

    finish(book, page, blocks, final, status, others, read_agreement, final_path, votes_path)
    counts = Counter(status.values())
    print(f"vote-text: page {page} stage {stage}: done. {counts.get('agreed', 0)} agreed, {counts.get('voted', 0)} voted, "
          f"{counts.get('unsure', 0)} unsure; text_agreement {text_agreement}.")


def finish(book, page, blocks, final, status, others, read_agreement, final_path, votes_path) -> None:
    doubts, needs_human, unknown = [], [], []
    vote_blocks = {}
    for blk in blocks:
        entry = {"text_status": status[blk.id], "read_agreement": float(read_agreement.get(blk.id, 0.0)),
                 "other_readings": others.get(blk.id, [])}
        if blk.bijoy_converted or blk.pdf_bijoy:
            entry["bijoy_converted"] = True
            entry["lang"] = "bn"
        vote_blocks[blk.id] = entry
        if status[blk.id] == "unsure":
            doubts.append(f"{blk.id}: the readers disagree; the best guess is kept with [?].")
        if blk.lang == "bn":
            for word in common.leftover_symbols(final[blk.id]):
                doubt = f"{blk.id}: unconverted symbol in {word}"
                if doubt not in doubts:
                    doubts.append(doubt)
                if blk.id not in needs_human:
                    needs_human.append(blk.id)
            for word in common.unknown_words(final[blk.id]):
                if word not in unknown:
                    unknown.append(word)
    common.save_json(final_path, {blk.id: final[blk.id] for blk in blocks})
    common.save_json(votes_path, {"blocks": vote_blocks, "unknown_words": unknown, "doubts": doubts,
                                  "needs_human": needs_human})
    if needs_human:
        book.add_tag(page, "needs_human")
    elif not book.has_tag(page, "latin_text"):
        book.remove_tag(page, "needs_human")


if __name__ == "__main__":
    common.run(main)
