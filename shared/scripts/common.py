"""Shared helper for every workflow script: paths, page names, book names, log.csv,
work folders, JSON checks and the Bangla text helpers.

Imported by the scripts (it has no hyphen so it can be imported), and also run by itself:

    python shared/scripts/common.py validate <file_path>
    python shared/scripts/common.py books <wf>
    python shared/scripts/common.py clear-work <wf> <book_name> <page>
    python shared/scripts/common.py set-status <wf> <book_name> <page> <status>
    python shared/scripts/common.py add-tag <wf> <book_name> <page> <tag>
    python shared/scripts/common.py remove-tag <wf> <book_name> <page> <tag>
    python shared/scripts/common.py set-note <wf> <book_name> <page> "<one plain sentence>"
    python shared/scripts/common.py add-note <wf> <book_name> <page> "<one plain sentence>"
    python shared/scripts/common.py show-log <wf> <book_name>
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

# The console on Windows may not be UTF-8; Bangla must still print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ----------------------------------------------------------------------------------------------
# Root and paths
# ----------------------------------------------------------------------------------------------

def find_root(start: Path | None = None) -> Path:
    """Go up from this file (or start) until the folder holding shared/ and CLAUDE.md."""
    here = Path(start or __file__).resolve()
    for folder in [here] + list(here.parents):
        if (folder / "shared").is_dir() and (folder / "CLAUDE.md").is_file():
            return folder
    raise SystemExit("Cannot find the repo root (the folder with shared/ and CLAUDE.md).")


ROOT = find_root()
INPUT_DIR = ROOT / "input"
REFERENCE_DIR = ROOT / "shared" / "reference"
WORD_LIST_PATH = REFERENCE_DIR / "bangla-words.txt"

STATUSES = ("new", "extracted", "redo", "done")
LOG_COLUMNS = ["page", "status", "confidence", "coverage", "text_agreement", "tags", "note"]
FAILED_NOTE = "This page could not be processed."


class StopError(Exception):
    """A plain sentence for the human; the script stops with an error code."""


def workflow_dir(wf: str) -> Path:
    path = ROOT / wf
    if not wf.startswith("WF_") or not path.is_dir():
        raise StopError(f"There is no workflow folder {wf}/ in the repo.")
    return path


def samples_input(wf: str) -> Path:
    return ROOT / "samples" / wf / "input"


def samples_output(wf: str) -> Path:
    return ROOT / "samples" / wf / "output"


_CONFIG_CACHE: dict[tuple[str, str], dict] = {}


def config(wf: str, name: str) -> dict:
    """Content of <wf>/config/<name>.json."""
    key = (wf, name)
    if key not in _CONFIG_CACHE:
        path = workflow_dir(wf) / "config" / f"{name}.json"
        try:
            _CONFIG_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise StopError(f"The config file {wf}/config/{name}.json is missing.")
    return _CONFIG_CACHE[key]


# ----------------------------------------------------------------------------------------------
# Page names
# ----------------------------------------------------------------------------------------------

def internal_page_name(n: int) -> str:
    """7 -> page-007 (pages/ and work/)."""
    return f"page-{int(n):03d}"


def output_page_name(n: int) -> str:
    """7 -> page_007 (renders and crops)."""
    return f"page_{int(n):03d}"


def page_number(name: str) -> int:
    """page-007, page_007, page_007.jpg, page-007.json -> 7."""
    match = re.search(r"page[-_](\d+)", name)
    if not match:
        raise ValueError(f"not a page name: {name}")
    return int(match.group(1))


# ----------------------------------------------------------------------------------------------
# Book names and PDFs
# ----------------------------------------------------------------------------------------------

def _is_bengali_char(ch: str) -> bool:
    return "ঀ" <= ch <= "৿"


def book_name_from_pdf(file_name: str) -> str:
    """Math-Book-PP.pdf -> math_book_pp. Bangla letters stay; anything else becomes _."""
    stem = Path(file_name).name
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]
    stem = unicodedata.normalize("NFC", stem).lower()
    out = []
    for ch in stem:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or _is_bengali_char(ch) or ch in "‌‍":
            out.append(ch)
        else:
            out.append("_")
    name = re.sub(r"_+", "_", "".join(out)).strip("_")
    return name or "book"


def is_sample(book_name: str) -> bool:
    return book_name.startswith("sample_")


def list_pdfs(wf: str) -> list[tuple[str, Path]]:
    """(book_name, path) for every PDF in input/ and samples/<wf>/input/."""
    found = []
    for folder in (INPUT_DIR, samples_input(wf)):
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.suffix.lower() == ".pdf":
                    found.append((book_name_from_pdf(path.name), path))
    return found


def pdf_for_book(wf: str, book_name: str) -> Path:
    folder = samples_input(wf) if is_sample(book_name) else INPUT_DIR
    matches = [p for name, p in list_pdfs(wf) if name == book_name and p.parent == folder]
    if not matches:
        raise StopError(f"No PDF gives the book name {book_name}.")
    if len(matches) > 1:
        raise StopError(
            f"Two PDFs give the same book name ({book_name}): {matches[0].name} and {matches[1].name}. "
            "Rename one of them.")
    return matches[0]


def pdf_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ----------------------------------------------------------------------------------------------
# Safe file writing
# ----------------------------------------------------------------------------------------------

def _replace_with_retry(tmp: Path, target: Path) -> None:
    """os.replace, retried: on Windows a reader or OneDrive can hold the target for a moment."""
    for attempt in range(50):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            time.sleep(0.1 + attempt * 0.02)
    os.replace(tmp, target)


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with open(tmp, "w", encoding=encoding, newline="\n") as handle:
        handle.write(text)
    _replace_with_retry(tmp, path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data)
    _replace_with_retry(tmp, path)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path: Path, data, check: bool = True) -> None:
    """Check against config/schema.json (when the path has a kind), then write to a temporary
    name and rename, so a crash never leaves a half-written file."""
    path = Path(path)
    if check:
        problems = validate_data(data, path)
        if problems:
            raise StopError(f"{path.name} does not match config/schema.json: {problems[0]}")
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def remove_path(path: Path) -> None:
    """Delete a file or folder, retrying for Windows locks and read-only files."""
    path = Path(path)
    if not path.exists():
        return

    def _on_error(func, target, _info):
        try:
            os.chmod(target, 0o700)
            func(target)
        except Exception:
            pass

    for attempt in range(20):
        try:
            if path.is_dir():
                if sys.version_info >= (3, 12):
                    shutil.rmtree(path, onexc=_on_error)
                else:
                    shutil.rmtree(path, onerror=_on_error)
            else:
                path.unlink()
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(0.1 + attempt * 0.05)
        if not path.exists():
            return
    if path.exists():
        raise StopError(f"Cannot delete {path}. Close any program that has it open, then run again.")


def move_path(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(20):
        try:
            shutil.move(str(src), str(dst))
            return
        except PermissionError:
            time.sleep(0.1 + attempt * 0.05)
    shutil.move(str(src), str(dst))


# ----------------------------------------------------------------------------------------------
# Schema checks
# ----------------------------------------------------------------------------------------------

_SCHEMA_CACHE: dict[Path, dict] = {}


def _workflow_of_path(path: Path) -> Path | None:
    try:
        rel = Path(path).resolve().relative_to(ROOT)
    except ValueError:
        return None
    if rel.parts and rel.parts[0].startswith("WF_"):
        return ROOT / rel.parts[0]
    return None


def kind_of(path: Path) -> str | None:
    """The kind of a JSON file, from its path and name. None means: no definition (only parse it)."""
    path = Path(path)
    name = path.name
    parent = path.parent.name
    parts = [p.lower() for p in path.parts]
    if parent == "config":
        return "schema" if name == "schema.json" else None
    if parent == "pages" and re.fullmatch(r"page-\d{3,}\.json", name):
        return "page"
    if name == "book-info.json":
        return "book_info"
    if name == "pdf-words.json":
        return "pdf_words"
    in_work = any(re.fullmatch(r"page-\d{3,}", p) for p in parts) and "work" in parts
    if in_work:
        simple = {"layout.json": "layout", "images.json": "images", "context.json": "context",
                  "votes.json": "votes", "leftovers.json": "leftovers", "ocr.json": "ocr"}
        if name in simple:
            return simple[name]
        if re.fullmatch(r"text-(a|b|c|final)\.json", name):
            return "reader_answer"
        if name == "scores.json" and parent == "try1":
            return "try_scores"
        return None
    # temp/<book_name>/<book_name>.json is the Book JSON
    if path.parent.parent.name == "temp" and name == f"{path.parent.name}.json":
        return "book"
    return None


def _schema_for(wf_path: Path) -> dict:
    schema_path = wf_path / "config" / "schema.json"
    if schema_path not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[schema_path] = read_json(schema_path)
    return _SCHEMA_CACHE[schema_path]


def validate_data(data, path: Path, kind: str | None = None) -> list[str]:
    """Problems of data as the file at path (empty list: ok)."""
    kind = kind or kind_of(path)
    if kind is None:
        return []
    wf_path = _workflow_of_path(path)
    if wf_path is None:
        return []
    import jsonschema  # imported here so the light commands work without it

    if kind == "schema":
        try:
            jsonschema.Draft202012Validator.check_schema(data)
        except jsonschema.SchemaError as err:
            return [f"schema.json is not a valid JSON Schema: {err.message}"]
        return []
    schema = _schema_for(wf_path)
    if kind not in schema.get("$defs", {}):
        return [f"config/schema.json has no definition called {kind}"]
    wrapper = {"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"}
    validator = jsonschema.Draft202012Validator(wrapper)
    problems = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "(top)"
        problems.append(f"at {where}: {err.message[:300]}")
    problems.extend(_extra_checks(data, kind))
    return problems


def _extra_checks(data, kind: str) -> list[str]:
    """Checks a JSON Schema cannot express: unique ids, box order, ids that exist."""
    problems = []

    def check_boxes(items, label):
        for item in items:
            box = item.get("box") if isinstance(item, dict) else None
            if isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
                if box[2] < box[0] or box[3] < box[1]:
                    problems.append(f"{label} {item.get('id', '')}: box must be [left, top, right, bottom]")

    def check_unique(items, label):
        seen = set()
        for item in items:
            if isinstance(item, dict) and "id" in item:
                if item["id"] in seen:
                    problems.append(f"{label}: the id {item['id']} is used twice")
                seen.add(item["id"])

    if kind == "layout" and isinstance(data, dict):
        blocks = data.get("text_blocks") or []
        check_unique(blocks, "text_blocks")
        check_boxes(blocks, "text block")
    if kind == "images" and isinstance(data, dict):
        images = data.get("images") or []
        check_unique(images, "images")
        check_boxes(images, "image block")
    if kind == "page" and isinstance(data, dict):
        blocks = data.get("text_blocks") or []
        images = data.get("images") or []
        check_unique(blocks, "text_blocks")
        check_unique(images, "images")
        check_boxes(blocks, "text block")
        check_boxes(images, "image block")
        ids = {b.get("id") for b in blocks if isinstance(b, dict)} | {i.get("id") for i in images if isinstance(i, dict)}
        context = data.get("context") or {}
        if isinstance(context, dict):
            used = []
            for key in ("heading_ids", "running_header_ids", "running_footer_ids", "reading_flow"):
                used += [v for v in context.get(key) or [] if isinstance(v, str)]
            for link in context.get("links") or []:
                if isinstance(link, dict):
                    used += [link.get("from"), link.get("to")]
            for block_id in used:
                if block_id not in ids:
                    problems.append(f"context uses the id {block_id}, which is not a block of this page")
    return problems


def validate(file_path) -> list[str]:
    """Check a saved JSON file against its definition in its workflow's config/schema.json."""
    path = Path(file_path)
    try:
        data = read_json(path)
    except FileNotFoundError:
        return [f"{path} does not exist"]
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        return [f"{path.name} is not valid JSON: {err}"]
    return validate_data(data, path)


# ----------------------------------------------------------------------------------------------
# Bangla text helpers
# ----------------------------------------------------------------------------------------------

_CONVERTER = None
_BIJOY_SYMBOLS: set[str] | None = None


def _converter():
    global _CONVERTER
    if _CONVERTER is None:
        try:
            from bijoy2unicode import converter as _b2u
        except ImportError:
            raise StopError("The package bijoy2unicode is missing. Run: pip install -r requirements.txt")
        _CONVERTER = _b2u.Unicode()
    return _CONVERTER


def bijoy_symbols() -> set[str]:
    """Non-ASCII characters that only appear in Bijoy-coded text (from the one conversion table)."""
    global _BIJOY_SYMBOLS
    if _BIJOY_SYMBOLS is None:
        try:
            from bijoy2unicode import converter as _b2u
            keys = "".join(_b2u.conversionMap.keys())
        except ImportError:
            keys = ""
        _BIJOY_SYMBOLS = {ch for ch in keys if ord(ch) > 127 and ch not in "‘’“”–—"}
    return _BIJOY_SYMBOLS


def has_bengali(text: str) -> bool:
    return any(_is_bengali_char(ch) for ch in text)


def _needs_bijoy_conversion(token: str) -> bool:
    if has_bengali(token):
        return False
    symbols = bijoy_symbols()
    return any(("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in symbols for ch in token)


def _convert_token(token: str) -> str:
    conv = _converter()
    try:
        out = conv.convertBijoyToUnicode(token)
    except Exception:
        try:
            out = conv.convertBijoyToUnicode(token + " ")
            if out.endswith(" "):
                out = out[:-1]
        except Exception:
            return token
    return unicodedata.normalize("NFC", out)


def bijoy_to_unicode(text: str, force: bool = False) -> str:
    """Convert Bijoy (SutonnyMJ and other legacy ANSI Bengali fonts) to Unicode Bengali.
    The only place the conversion is written. Uses the conversion table of the bijoy2unicode
    package (MIT). Words that already hold Bengali letters, and the [?] mark, are left as they are.
    Without force, only words with Latin letters or Bijoy symbols are converted; with force (text
    known to be in a Bijoy font) digits and signs are converted too. A word the converter cannot
    handle is kept unchanged."""
    if not text:
        return text
    parts = re.split(r"(\s+|\[\?\])", text)
    out = []
    for part in parts:
        if not part or part.isspace() or part == "[?]" or has_bengali(part):
            out.append(part)
        elif force or _needs_bijoy_conversion(part):
            out.append(_convert_token(part))
        else:
            out.append(part)
    return unicodedata.normalize("NFC", "".join(out))


_BIJOY_FONT_RE = re.compile(r"(mj$|sutonny|bijoy|ansi|nikoshban|^amarbangla$|^chandrabati|^sulekha)")


def is_bijoy_font(font_name: str) -> bool:
    """True for legacy ANSI Bengali fonts (SutonnyMJ and the like), whose text is Bijoy code."""
    name = re.sub(r"^[A-Z]{6}\+", "", font_name or "")
    name = re.split(r"[-,]", name)[0].replace(" ", "").lower()
    name = re.sub(r"(bold|italic|regular|normal|oblique)+$", "", name)
    return bool(_BIJOY_FONT_RE.search(name))


def is_bijoy_latin(text: str) -> bool:
    """True when a text of a Bengali block holds Latin letters (or Bijoy symbols) as at least half
    of its letters, so it is Bijoy code and must be converted."""
    symbols = bijoy_symbols()
    latin = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in symbols)
    bengali = sum(1 for ch in text if _is_bengali_char(ch) and unicodedata.category(ch).startswith("L"))
    return latin > 0 and latin >= bengali


def latin_share(text: str) -> float:
    """Share of letters that are Latin A-Z/a-z (digits, spaces and punctuation not counted)."""
    latin = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    letters = sum(1 for ch in text if ch.isalpha() or (_is_bengali_char(ch) and unicodedata.category(ch)[0] in "LM"))
    return latin / letters if letters else 0.0


EDGE_PUNCT = "\"'`.,;:!?()[]{}<>«»‘’“”-–—।॥/\\*_~|"
_SIGN_CHARS = set("'`~^&|\\@#$%*_=+<>{}[]\"") | {chr(c) for c in range(ord("A"), ord("Z") + 1)} | \
    {chr(c) for c in range(ord("a"), ord("z") + 1)}


def leftover_symbols(text: str) -> list[str]:
    """Words of Bengali text that still hold an ASCII sign (or a Bijoy symbol) after conversion."""
    found = []
    symbols = bijoy_symbols()
    for token in text.replace("[?]", " ").split():
        core = token.strip(EDGE_PUNCT)
        if not core or not has_bengali(core):
            continue
        if any(ch in _SIGN_CHARS or ch in symbols for ch in core):
            found.append(token)
    return found


_SPACES = re.compile(r"[   -   　\t]")
_QUOTE_MAP = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
              "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
              "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
              "−": "-"}


def clean_text(text: str) -> str:
    """Unicode NFC, one kind of space, quote mark and dash. Never changes letters. Keeps line breaks."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)
    text = "".join(_QUOTE_MAP.get(ch, ch) for ch in text)
    text = re.sub(r" {2,}", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def compare_form(text: str) -> str:
    """clean_text with every run of white space (line breaks too) made one space: for comparing."""
    return re.sub(r"\s+", " ", clean_text(text)).strip()


def char_diff(a: str, b: str) -> tuple[int, int]:
    """(differing characters, all characters) between two compare forms."""
    total = max(len(a), len(b))
    if total == 0:
        return 0, 0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = sum(block.size for block in matcher.get_matching_blocks())
    return total - same, total


def word_agreement(a: str, b: str) -> float:
    """Share of words that match (0 to 1)."""
    wa, wb = a.split(), b.split()
    if not wa and not wb:
        return 1.0
    return round(difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio(), 4)


def looks_like_unicode_bangla(text: str) -> bool:
    """Real Bangla Unicode letters in a possible order (no word starts with a vowel sign or a
    hasanta, no Latin letters). Text extracted in visual order fails this check."""
    if not has_bengali(text):
        return False
    if any(ch.isalpha() and not _is_bengali_char(ch) for ch in text):
        return False
    for token in text.split():
        core = token.strip(EDGE_PUNCT)
        if not core:
            continue
        first = core[0]
        if _is_bengali_char(first) and unicodedata.category(first).startswith("M"):
            return False
        if "্্" in core:
            return False
    return True


_WORDS: set[str] | None = None


def word_list() -> set[str]:
    """The Bangla word list (a hint only)."""
    global _WORDS
    if _WORDS is None:
        _WORDS = set()
        if WORD_LIST_PATH.is_file():
            with open(WORD_LIST_PATH, encoding="utf-8") as handle:
                for line in handle:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        _WORDS.add(unicodedata.normalize("NFC", word))
    return _WORDS


# Common Bangla word endings (case, number and article endings), longest first. The word list holds
# stems, so a word is known if it, or what is left after removing one or two of these, is in it.
_ENDINGS = sorted({
    "গুলোকে", "গুলোতে", "গুলোর", "গুলো", "গুলিকে", "গুলির", "গুলি", "দেরকে", "দেরই", "দের", "েরা", "রা",
    "য়েরা", "দিগকে", "দিগের", "সমূহের", "সমূহ", "বৃন্দ", "মালা", "টিকে", "টির", "টিতে", "টি", "টাকে", "টার",
    "টাতে", "টা", "খানা", "খানি", "টুকু", "য়ের", "য়ে", "য়", "েরও", "েরই", "ের", "এর", "র", "কে", "তে", "েতে",
    "ে", "েই", "েও", "ই", "ও", "রও", "রই", "কেও", "কেই", "তেও", "তেই",
    # verb endings (the list holds verbal nouns such as পড়া, so a verb stem is also tried with া)
    "েছিলাম", "েছিলে", "েছিলেন", "েছিল", "েছিস", "েছেন", "েছে", "েছি", "েছ", "ছিলাম", "ছিলেন", "ছিলে",
    "ছিল", "ছেন", "ছে", "ছি", "ছ", "লাম", "লেন", "লে", "ল", "বেন", "বে", "ব", "বো", "তাম", "তেন", "ত",
    "ুন", "ুক", "েন", "িস", "িলে", "িয়া", "িয়ে", "িতে", "িবে", "িল", "াও", "ান", "ায়", "ি", "ো", "ে",
}, key=len, reverse=True)


def _known(core: str, words: set[str], depth: int = 2) -> bool:
    if core in words or core + "া" in words:
        return True
    if depth == 0:
        return False
    for ending in _ENDINGS:
        if core.endswith(ending) and len(core) - len(ending) >= 2:
            stem = core[: -len(ending)]
            if _known(stem, words, depth - 1):
                return True
    return False


def unknown_words(text: str) -> list[str]:
    """Bengali words of text that are not in the word list (a hint only)."""
    words = word_list()
    if not words:
        return []
    found = []
    for token in text.replace("[?]", " ").split():
        core = token.strip(EDGE_PUNCT + "০১২৩৪৫৬৭৮৯0123456789")
        if not core or not has_bengali(core):
            continue
        core = unicodedata.normalize("NFC", core)
        if core not in found and not _known(core, words):
            found.append(core)
    return found


# ----------------------------------------------------------------------------------------------
# Boxes and PDF words
# ----------------------------------------------------------------------------------------------

def clip_box(box, width: int, height: int):
    """Cut a box back to the page. None when no area is left."""
    left, top, right, bottom = [float(v) for v in box]
    left, right = max(0.0, min(left, width)), max(0.0, min(right, width))
    top, bottom = max(0.0, min(top, height)), max(0.0, min(bottom, height))
    if right - left < 1 or bottom - top < 1:
        return None
    return [int(round(left)), int(round(top)), int(round(right)), int(round(bottom))]


def boxes_overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def assign_words(words: list[dict], blocks: list[dict], margin: float = 4.0) -> dict[str, list[dict]]:
    """Put every PDF word into the text block whose box holds its centre (the smallest one)."""
    result = {b["id"]: [] for b in blocks}
    for word in words:
        l, t, r, b = word["box"]
        cx, cy = (l + r) / 2, (t + b) / 2
        best, best_area = None, None
        for block in blocks:
            bl, bt, br, bb = block["box"]
            if bl - margin <= cx <= br + margin and bt - margin <= cy <= bb + margin:
                area = (br - bl) * (bb - bt)
                if best is None or area < best_area:
                    best, best_area = block["id"], area
        if best is not None:
            result[best].append(word)
    return result


def words_in_reading_order(words: list[dict]) -> str:
    """Join words line by line (top to bottom, left to right)."""
    if not words:
        return ""
    heights = sorted(w["box"][3] - w["box"][1] for w in words)
    tolerance = max(2.0, heights[len(heights) // 2] * 0.5)
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: ((w["box"][1] + w["box"][3]) / 2, w["box"][0])):
        cy = (word["box"][1] + word["box"][3]) / 2
        if lines:
            last = lines[-1]
            last_cy = sum((w["box"][1] + w["box"][3]) / 2 for w in last) / len(last)
            if abs(cy - last_cy) <= tolerance:
                last.append(word)
                continue
        lines.append([word])
    return "\n".join(" ".join(w["text"] for w in sorted(line, key=lambda w: w["box"][0])) for line in lines)


# ----------------------------------------------------------------------------------------------
# Word (.docx) helpers, shared by every script that builds a .docx
# ----------------------------------------------------------------------------------------------

BANGLA_FONT = "Noto Sans Bengali"


def docx_set_run_font(run, font_name: str | None = None, size_pt: float | None = None,
                      bold: bool | None = None, italic: bool | None = None, color: str | None = None) -> None:
    """Style a python-docx run for Latin and Bangla (complex script) text alike.
    A legacy Bijoy font name is never applied to Unicode text: the Bangla font is used instead."""
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    name = font_name.strip() if font_name else ""
    if not name or is_bijoy_font(name):
        name = BANGLA_FONT
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, fonts)
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(key), name)
    if size_pt:
        size_pt = max(1.0, min(float(size_pt), 400.0))
        run.font.size = Pt(size_pt)
        _docx_flag(rpr, "w:szCs", str(int(round(size_pt * 2))))
    if bold is not None:
        run.font.bold = bool(bold)
        _docx_flag(rpr, "w:bCs", None if bold else "0")
    if italic is not None:
        run.font.italic = bool(italic)
        _docx_flag(rpr, "w:iCs", None if italic else "0")
    if color and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        run.font.color.rgb = RGBColor.from_string(color[1:].upper())


def _docx_flag(rpr, tag: str, value: str | None) -> None:
    from docx.oxml.ns import qn
    element = rpr.find(qn(tag))
    if element is None:
        element = rpr.makeelement(qn(tag), {})
        rpr.append(element)
    if value is None:
        element.attrib.pop(qn("w:val"), None)
    else:
        element.set(qn("w:val"), value)


def docx_new_document():
    """A new Word document whose default font is the Bangla font."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    document = Document()
    for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Title"):
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        style.font.name = BANGLA_FONT
        rpr = style.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = rpr.makeelement(qn("w:rFonts"), {})
            rpr.insert(0, fonts)
        for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(key), BANGLA_FONT)
        for theme_key in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            fonts.attrib.pop(qn(theme_key), None)
    document.styles["Normal"].font.size = Pt(11)
    return document


def docx_alignment(align: str):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    return {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}.get(align)


def docx_add_text(document, text: str, *, bold: bool = False, italic: bool = False, size_pt: float | None = None,
                  color: str | None = None, font_name: str | None = None, align: str | None = None, style=None):
    """One paragraph; line breaks inside text become line breaks in Word."""
    paragraph = document.add_paragraph(style=style)
    lines = (text or "").split("\n")
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        docx_set_run_font(run, font_name, size_pt, bold, italic, color)
        if index < len(lines) - 1:
            run.add_break()
    if align:
        paragraph.alignment = docx_alignment(align)
    return paragraph


def docx_save(document, path: Path) -> Path:
    """Save through a temporary name and rename. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}.tmp-{os.getpid()}{path.suffix}")
    document.save(str(tmp))
    _replace_with_retry(tmp, path)
    return path


# ----------------------------------------------------------------------------------------------
# One book of one workflow
# ----------------------------------------------------------------------------------------------

class Book:
    """Every path of one book in one workflow, its log.csv and its work folders."""

    def __init__(self, wf: str, book_name: str):
        self.wf = wf
        self.wf_dir = workflow_dir(wf)
        if not book_name or book_name != book_name_from_pdf(book_name + ".pdf"):
            raise StopError(f"{book_name} is not a book name. List the book names with: "
                            f"python shared/scripts/common.py books {wf}")
        self.name = book_name
        self.temp = self.wf_dir / "temp" / book_name
        self.renders = self.temp / "renders"
        self.pages = self.temp / "pages"
        self.images = self.temp / "images"
        self.work_root = self.temp / "work"
        self.book_info_path = self.temp / "book-info.json"
        self.pdf_words_path = self.temp / "pdf-words.json"
        self.log_path = self.temp / "log.csv"
        self.lock_path = self.temp / "log.csv.lock"
        self.review_path = self.temp / f"{book_name}_review.docx"
        self.book_json_path = self.temp / f"{book_name}.json"
        self.book_md_path = self.temp / f"{book_name}.md"
        self.book_docx_path = self.temp / f"{book_name}.docx"
        self.output_root = self.wf_dir / "output"
        self._book_info = None
        self._pdf_words = None

    # -- paths ---------------------------------------------------------------------------------
    @property
    def pdf_path(self) -> Path:
        return pdf_for_book(self.wf, self.name)

    @property
    def is_sample(self) -> bool:
        return is_sample(self.name)

    def config(self, name: str) -> dict:
        return config(self.wf, name)

    def work(self, page: int) -> Path:
        return self.work_root / internal_page_name(page)

    def page_json_path(self, page: int) -> Path:
        return self.pages / f"{internal_page_name(page)}.json"

    def render_path(self, page: int) -> Path:
        return self.renders / f"{output_page_name(page)}.jpg"

    def crop_path(self, page: int, image_id: str, ext: str) -> Path:
        return self.images / f"{output_page_name(page)}_{image_id}.{ext}"

    def crops_of_page(self, page: int) -> list[Path]:
        if not self.images.is_dir():
            return []
        prefix = f"{output_page_name(page)}_"
        return sorted(p for p in self.images.iterdir() if p.name.startswith(prefix))

    def existing_crop(self, page: int, image_id: str) -> Path | None:
        for ext in ("jpg", "png"):
            path = self.crop_path(page, image_id, ext)
            if path.is_file():
                return path
        return None

    # -- book-wide files -----------------------------------------------------------------------
    def book_info_all(self) -> dict:
        if self._book_info is None:
            if not self.book_info_path.is_file():
                raise StopError(f"book-info.json of {self.name} is missing. Run cut-pages.py {self.name} first.")
            self._book_info = read_json(self.book_info_path)
        return self._book_info

    def book_info(self, page: int) -> dict:
        entry = self.book_info_all()["pages"].get(output_page_name(page))
        if entry is None:
            raise StopError(f"Page {page} of {self.name} has no render (it could not be drawn).")
        return entry

    def page_count(self) -> int:
        return len(self.read_log())

    def pdf_words(self, page: int) -> dict | None:
        """One page's words from pdf-words.json, or None if the page has none."""
        if self._pdf_words is None:
            self._pdf_words = read_json(self.pdf_words_path) if self.pdf_words_path.is_file() else {"pages": {}}
        return self._pdf_words["pages"].get(output_page_name(page))

    # -- log.csv -------------------------------------------------------------------------------
    def _with_lock(self, func):
        cfg = self.config("run").get("log_lock", {})
        wait_s, stale_s = float(cfg.get("wait_s", 30)), float(cfg.get("stale_s", 60))
        self.temp.mkdir(parents=True, exist_ok=True)
        started = time.time()
        while True:
            try:
                handle = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(handle, str(os.getpid()).encode())
                os.close(handle)
                break
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > stale_s:
                        self.lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.time() - started > wait_s:
                    raise StopError("log.csv stayed locked by another script. Run this step again.")
                time.sleep(0.05)
            except PermissionError:
                time.sleep(0.05)
        try:
            return func()
        finally:
            for _ in range(20):
                try:
                    self.lock_path.unlink()
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.05)

    def _read_rows(self) -> list[dict]:
        if not self.log_path.is_file():
            return []
        for attempt in range(20):
            try:
                with open(self.log_path, encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                break
            except PermissionError:
                time.sleep(0.05 + attempt * 0.02)
        else:
            raise StopError("log.csv cannot be read. Close it in any other program, then run again.")
        return [{col: (row.get(col) or "") for col in LOG_COLUMNS} for row in rows]

    def _write_rows(self, rows: list[dict]) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=LOG_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: int(r["page"])):
            writer.writerow(row)
        write_text_atomic(self.log_path, buffer.getvalue(), encoding="utf-8-sig")

    def ensure_log(self, page_count: int) -> None:
        """Create log.csv with one row per page (status new) if it is missing; add missing rows."""
        def work():
            rows = self._read_rows()
            have = {int(r["page"]) for r in rows}
            changed = False
            for n in range(1, page_count + 1):
                if n not in have:
                    rows.append({"page": str(n), "status": "new", "confidence": "", "coverage": "",
                                 "text_agreement": "", "tags": "", "note": ""})
                    changed = True
            if changed or not self.log_path.is_file():
                self._write_rows(rows)
        self._with_lock(work)

    def read_log(self) -> dict[int, dict]:
        rows = self._read_rows()
        if not rows:
            raise StopError(f"log.csv of {self.name} is missing. Run cut-pages.py {self.name} first.")
        return {int(r["page"]): r for r in rows}

    def row(self, page: int) -> dict:
        row = self.read_log().get(int(page))
        if row is None:
            raise StopError(f"Page {page} is not a page of {self.name}.")
        return row

    def update_row(self, page: int, change) -> dict:
        """change(row) edits one page's row in place, under the lock."""
        def work():
            rows = self._read_rows()
            for row in rows:
                if int(row["page"]) == int(page):
                    change(row)
                    self._write_rows(rows)
                    return row
            raise StopError(f"Page {page} is not a page of {self.name}.")
        return self._with_lock(work)

    def set_columns(self, page: int, **values) -> dict:
        for key in values:
            if key not in LOG_COLUMNS or key in ("page", "tags", "note", "status"):
                raise StopError(f"set_columns cannot change the column {key}.")

        def change(row):
            for key, value in values.items():
                row[key] = "" if value is None else str(value)
        return self.update_row(page, change)

    def set_status(self, page: int, status: str) -> dict:
        if status not in STATUSES:
            raise StopError(f"{status} is not a status. Use one of: {', '.join(STATUSES)}.")

        def change(row):
            row["status"] = status
        return self.update_row(page, change)

    @staticmethod
    def tags_of(row: dict) -> list[str]:
        return [t for t in row.get("tags", "").split(";") if t]

    def add_tag(self, page: int, tag: str) -> dict:
        def change(row):
            tags = self.tags_of(row)
            if tag not in tags:
                tags.append(tag)
            row["tags"] = ";".join(tags)
        return self.update_row(page, change)

    def remove_tag(self, page: int, tag: str) -> dict:
        def change(row):
            row["tags"] = ";".join(t for t in self.tags_of(row) if t != tag)
        return self.update_row(page, change)

    def has_tag(self, page: int, tag: str) -> bool:
        return tag in self.tags_of(self.row(page))

    def set_note(self, page: int, sentence: str) -> dict:
        def change(row):
            row["note"] = " ".join(sentence.split())
        return self.update_row(page, change)

    def add_note(self, page: int, sentence: str) -> dict:
        sentence = " ".join(sentence.split())

        def change(row):
            note = row.get("note", "")
            if sentence and sentence not in note:
                row["note"] = (note + " " + sentence).strip()
        return self.update_row(page, change)

    def remove_note_part(self, page: int, part: str) -> dict:
        """Remove every sentence of the note that contains part."""
        def change(row):
            sentences = re.split(r"(?<=[.!?])\s+", row.get("note", ""))
            row["note"] = " ".join(s for s in sentences if s and part not in s)
        return self.update_row(page, change)

    # -- work folders --------------------------------------------------------------------------
    def clear_work(self, page: int) -> Path:
        """Create work/page-XXX/ if missing and empty it, except its try1/ folder."""
        folder = self.work(page)
        folder.mkdir(parents=True, exist_ok=True)
        for item in folder.iterdir():
            if item.name != "try1":
                remove_path(item)
        return folder

    # -- errors --------------------------------------------------------------------------------
    def fail(self, page: int | None, sentence: str):
        """Print the sentence, write it in the note column of that page's row, stop with an error code."""
        print(sentence)
        if page is not None and self.log_path.is_file():
            try:
                self.add_note(page, sentence)
            except Exception:
                pass
        sys.exit(1)


# ----------------------------------------------------------------------------------------------
# Script start
# ----------------------------------------------------------------------------------------------

def start(script_file: str, page: str = "none", usage: str = "") -> tuple[Book, int | None, list[str]]:
    """Read the arguments of a workflow script: <book_name> [page] [more].
    page is 'none', 'required' or 'optional'. The workflow is the folder above the script's scripts/."""
    wf = Path(script_file).resolve().parent.parent.name
    args = sys.argv[1:]
    script = Path(script_file).name
    if not args:
        raise StopError(f"Give the book name: python {wf}/scripts/{script} <book_name> {usage}".strip())
    book = Book(wf, args[0])
    page_number_value = None
    rest = args[1:]
    if page in ("required", "optional"):
        if rest and re.fullmatch(r"\d+", rest[0]):
            page_number_value = int(rest[0])
            rest = rest[1:]
            if page_number_value < 1:
                raise StopError("Page numbers start at 1.")
        elif page == "required":
            raise StopError(f"Give the page number: python {wf}/scripts/{script} {book.name} <page> {usage}".strip())
    return book, page_number_value, rest


def run(main) -> None:
    """Run a script's main(); a StopError prints its one plain sentence and stops with code 1."""
    try:
        main()
    except StopError as err:
        print(str(err))
        sys.exit(1)


# ----------------------------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------------------------

def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    command, rest = args[0], args[1:]

    if command == "validate":
        if len(rest) != 1:
            raise StopError("Use: python shared/scripts/common.py validate <file_path>")
        problems = validate(rest[0])
        if problems:
            print(f"problem in {rest[0]}:")
            for problem in problems[:20]:
                print(f"- {problem}")
            sys.exit(1)
        print("ok")
        return

    if command == "books":
        if len(rest) != 1:
            raise StopError("Use: python shared/scripts/common.py books <wf>")
        wf = rest[0]
        workflow_dir(wf)
        pdfs = list_pdfs(wf)
        if not pdfs:
            print("No PDFs in input/ or in samples/" + wf + "/input/.")
        by_name: dict[str, list[Path]] = {}
        for name, path in pdfs:
            by_name.setdefault(name, []).append(path)
            where = path.relative_to(ROOT).as_posix()
            sample = " (sample)" if path.parent == samples_input(wf) else ""
            finished = (ROOT / wf / "output" / name).is_dir()
            started = (ROOT / wf / "temp" / name).is_dir()
            state = "finished" if finished else ("started" if started else "not started")
            print(f"{where} -> {name}{sample} [{state}]")
        conflicts = 0
        for name, paths in by_name.items():
            if len(paths) > 1:
                conflicts += 1
                print(f"conflict: Two PDFs give the same book name ({name}): {paths[0].name} and "
                      f"{paths[1].name}. Rename one of them.")
        if conflicts:
            sys.exit(1)
        return

    book_commands = {"clear-work": 1, "set-status": 2, "add-tag": 2, "remove-tag": 2,
                     "set-note": 2, "add-note": 2, "show-log": 0}
    if command not in book_commands:
        raise StopError(f"Unknown command {command}. Run python shared/scripts/common.py for the list.")
    need = 2 + book_commands[command]
    if len(rest) < need:
        raise StopError(f"Not enough arguments for {command}. Run python shared/scripts/common.py for the list.")
    book = Book(rest[0], rest[1])
    if command == "show-log":
        for page, row in sorted(book.read_log().items()):
            print(",".join(row[c] for c in LOG_COLUMNS))
        return
    if not re.fullmatch(r"\d+", rest[2]):
        raise StopError(f"{rest[2]} is not a page number.")
    page = int(rest[2])
    if command == "clear-work":
        folder = book.clear_work(page)
        print(f"ok: emptied {folder.relative_to(ROOT).as_posix()} (try1/ kept)")
    elif command == "set-status":
        book.set_status(page, rest[3])
        print(f"ok: page {page} is {rest[3]}")
    elif command == "add-tag":
        book.add_tag(page, rest[3])
        print(f"ok: page {page} has the tag {rest[3]}")
    elif command == "remove-tag":
        book.remove_tag(page, rest[3])
        print(f"ok: page {page} no longer has the tag {rest[3]}")
    elif command == "set-note":
        book.set_note(page, " ".join(rest[3:]))
        print(f"ok: note of page {page} set")
    elif command == "add-note":
        book.add_note(page, " ".join(rest[3:]))
        print(f"ok: note added to page {page}")


if __name__ == "__main__":
    run(_cli)
