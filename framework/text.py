_REPLACEMENTS = {
    "–": "-",   # en dash
    "—": "-",   # em dash
    "−": "-",   # minus sign
    "“": '"',
    "”": '"',
    "„": '"',
    "’": "'",
    "‘": "'",
    "…": "...",
    "\u00a0": " ",  # non-breaking space
}

def sanitize_for_bitmap8(s: str) -> str:
    out = []

    for ch in s:
        # explicit replacements first
        if ch in _REPLACEMENTS:
            out.append(_REPLACEMENTS[ch])
            continue

        o = ord(ch)

        # allow printable ASCII + newline
        if ch == "\n" or 32 <= o <= 126:
            out.append(ch)
        else:
            out.append("?")  # or " " if you prefer

    return "".join(out)

def wrap_words(
    display,
    text: str,
    width: int,
    margin: int = 10,
    scale: int = 1,
    spacing: int = 1,
) -> list[str]:
    """
    Wrap `text` into lines that fit in the drawable area using `display.measure_text`.

    - Uses symmetric horizontal margins: usable width is `width - 2*margin`.
    - Preserves explicit newlines.
    - Wraps on word boundaries when possible.
    - If a single word is too wide, falls back to character-level wrapping for that word.
    """
    if text is None:
        text = ""

    # Preserve poetry formatting: keep empty lines; do not invent placeholder text.
    if text == "":
        return [""]

    max_line_px = width - (margin * 2)
    if max_line_px <= 0:
        return [""]

    def measure(s: str) -> int:
        # Must match your rendering: you call .upper() when drawing.
        return display.measure_text(s.upper(), scale, spacing)

    out: list[str] = []

    # Preserve explicit newline intent by forcing flush per line.
    # Note: splitlines() drops trailing blank lines; we preserve them below.
    raw_lines = text.splitlines()
    trailing_newlines = 0
    i = len(text) - 1
    while i >= 0 and text[i] == "\n":
        trailing_newlines += 1
        i -= 1

    for raw_line in raw_lines:
        words = raw_line.split()
        current = ""

        for w in words:
            candidate = w if not current else f"{current} {w}"
            if measure(candidate) <= max_line_px:
                current = candidate
                continue

            # candidate doesn't fit; flush current if it exists
            if current:
                out.append(current)
                current = ""

            # If the word itself fits on an empty line, start it
            if measure(w) <= max_line_px:
                current = w
                continue

            # Word is too long: character-wrap it
            chunk = ""
            for ch in w:
                cand2 = ch if not chunk else chunk + ch
                if measure(cand2) <= max_line_px:
                    chunk = cand2
                else:
                    if chunk:
                        out.append(chunk)
                    chunk = ch
            if chunk:
                current = chunk  # continue the line with the remainder

        # flush end of this explicit line
        if words:
            out.append(current)
        else:
            # original input had a blank line
            out.append("")

    # Preserve trailing blank lines (splitlines() drops them)
    # If text ends with N newlines, that implies N trailing blank lines.
    for _ in range(trailing_newlines):
        out.append("")

    return out