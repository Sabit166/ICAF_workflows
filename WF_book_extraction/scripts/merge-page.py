"""Join the working files of one page into pages/page-XXX.json.

    python WF_book_extraction/scripts/merge-page.py <book_name> <page>

Reads layout.json, images.json, context.json, text-final.json and votes.json from work/page-XXX/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                            if (p / "shared").is_dir() and (p / "CLAUDE.md").is_file()) / "shared" / "scripts"))
import common  # noqa: E402
from common import StopError  # noqa: E402

IMAGE_KEYS = ["id", "file", "box", "kind", "summary", "description", "purpose", "style", "main_colors",
              "layer", "rotation_deg", "opacity", "overlaps_text", "rebuild_notes"]


def main() -> None:
    book, page, _ = common.start(__file__, "required")
    work = book.work(page)
    files = {}
    for name in ("layout.json", "images.json", "context.json", "text-final.json", "votes.json"):
        path = work / name
        if not path.is_file():
            book.fail(page, f"This page could not be merged: {name} is missing.")
        files[name] = common.read_json(path)
    layout, images, context = files["layout.json"], files["images.json"], files["context.json"]
    final, votes = files["text-final.json"], files["votes.json"]
    entry = book.book_info(page)
    width, height = entry["width"], entry["height"]
    doubts: list[str] = []

    text_blocks = []
    for block in sorted(layout.get("text_blocks", []), key=lambda b: b.get("order", 0)):
        box = common.clip_box(block["box"], width, height)
        if box is None:
            doubts.append(f"{block['id']}: its box has no area on the page, so the block was left out.")
            continue
        vote = votes.get("blocks", {}).get(block["id"])
        if vote is None:
            vote = {"text_status": "unsure", "read_agreement": 0.0, "other_readings": []}
            doubts.append(f"{block['id']}: no vote was found for this block.")
        text = final.get(block["id"])
        if text is None:
            text = "[?]"
            doubts.append(f"{block['id']}: no final text was found for this block.")
        text_blocks.append({
            "id": block["id"], "type": block["type"], "lang": vote.get("lang") or block["lang"], "text": text,
            "text_status": vote["text_status"], "box": box, "font": block["font"], "align": block["align"],
            "order": block["order"], "read_agreement": vote["read_agreement"],
            "other_readings": vote.get("other_readings", []),
        })

    image_blocks = []
    for image in images.get("images", []):
        box = common.clip_box(image["box"], width, height)
        if box is None:
            doubts.append(f"{image['id']}: its box has no area on the page, so the image block was left out.")
            continue
        crop = book.existing_crop(page, image["id"])
        if crop is None:
            doubts.append(f"{image['id']}: no crop exists for this image block, so it was left out.")
            continue
        merged = dict(image)
        merged["box"] = box
        merged["file"] = f"images/{crop.name}"
        merged["overlaps_text"] = [b["id"] for b in text_blocks if common.boxes_overlap(box, b["box"])]
        image_blocks.append({key: merged[key] for key in IMAGE_KEYS})

    background = dict(images["background"])
    background["boxes"] = [b for b in (common.clip_box(x, width, height) for x in background.get("boxes", [])) if b]

    ids = {b["id"] for b in text_blocks} | {i["id"] for i in image_blocks}
    context = dict(context)
    removed = set()
    for key in ("heading_ids", "running_header_ids", "running_footer_ids", "reading_flow"):
        kept = [x for x in context.get(key, []) if x in ids]
        removed |= set(context.get(key, [])) - set(kept)
        context[key] = kept
    links = []
    for link in context.get("links", []):
        if link.get("from") in ids and link.get("to") in ids:
            links.append(link)
        else:
            removed |= {link.get("from"), link.get("to")} - ids
    context["links"] = links
    if removed:
        doubts.append(f"context named ids that are not blocks of this page ({', '.join(sorted(map(str, removed)))}); "
                      "they were removed.")

    page_json = {
        "page": page,
        "size": {"width": width, "height": height},
        "background": background,
        "text_blocks": text_blocks,
        "images": image_blocks,
        "context": context,
        "unknown_words": votes.get("unknown_words", []),
        "doubts": list(layout.get("doubts", [])) + list(images.get("doubts", [])) + list(votes.get("doubts", [])) + doubts,
    }
    try:
        common.save_json(book.page_json_path(page), page_json)
    except StopError as err:
        book.fail(page, f"This page could not be merged: {err}")
    print(f"merge-page: page {page}: {len(text_blocks)} text blocks, {len(image_blocks)} image blocks, "
          f"{len(page_json['doubts'])} doubts -> pages/{common.internal_page_name(page)}.json")


if __name__ == "__main__":
    common.run(main)
