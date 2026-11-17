---
name: bangla-text
description: "The Bangla text rules: verbatim, Unicode NFC, Bijoy text. Use when reading, comparing or checking Bangla text."
user-invocable: false
---

# Bangla text rules

This is the only copy of these rules.

- **Verbatim.** Save the letters exactly as printed. Never fix spelling, never guess missing letters,
  never make a sentence sensible. Write [?] where a part is unreadable or unsure.
- **Unicode.** Save and compare text in Unicode NFC. When comparing, use one kind of space, quote mark
  and dash. Never change letters.
- **Bijoy and ANSI text.** The PDF's hidden text is often in old-style fonts (Bijoy, SutonnyMJ) and
  looks like nonsense. It is stored in visual order, so it fails any Unicode check. Convert it to
  Unicode first, and only with bijoy_to_unicode() in shared/scripts/common.py (one conversion table).
  Never change letters by hand or by guess. Never discard converted text: if it still looks wrong,
  keep it in the vote and flag it.
- **Converter crashes.** Add a trailing space to the word before converting it and remove it
  afterwards. If the converter still fails on a word, keep the word as it is and go on. Never stop
  the run.
- **The PDF's own text is a reader, never the only one.** A disagreement with it always triggers
  another Claude reading. Latin letters (Pc, Rj, NU and the like) inside Bengali text are Bijoy code,
  not English: the vote script converts them, never an agent. A symbol such as ' or another ASCII
  sign left inside a Bengali word after conversion is a doubt, and a human fixes it.
- **Word list.** shared/reference/bangla-words.txt is only a hint. Names and rare forms show up as
  unknown even when they are correct.
- **Most common mistakes:** joined letters (যুক্তবর্ণ like ক্ষ, ন্ত) and vowel signs (ি, ু, ঁ).
  Look at these first.
