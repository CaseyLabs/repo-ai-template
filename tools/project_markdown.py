"""Small standard-library Markdown helpers shared by project workflow tools."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def mask_code(text: str) -> str:
    """Replace fenced and inline code with spaces while preserving newlines."""
    lines = text.splitlines(keepends=True)
    in_fence = None
    out = []
    for line in lines:
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if in_fence:
            out.append("".join("\n" if c == "\n" else " " for c in line))
            if m and m.group(1)[0] == in_fence[0] and len(m.group(1)) >= len(in_fence):
                in_fence = None
            continue
        if m:
            in_fence = m.group(1)
            out.append("".join("\n" if c == "\n" else " " for c in line))
        else:
            out.append(line)
    text = "".join(out)
    return re.sub(r"(`+)([^`\n]*?)\1", lambda m: " " * len(m.group(0)), text)


def slugify(heading: str) -> str:
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"`([^`]*)`", r"\1", heading)
    heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
    heading = heading.lower()
    heading = re.sub(r"[^\w\- ]", "", heading.strip(), flags=re.UNICODE)
    # GitHub turns each space into a hyphen without collapsing runs: "A / B" -> "a--b".
    return heading.replace(" ", "-")


def mask_fences(lines: list[str]) -> list[str]:
    """Blank fenced code block lines, keeping line indexes, so `# comment` lines are not headings."""
    cleaned_lines = []
    in_fence = None
    for line in lines:
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if in_fence:
            cleaned_lines.append("")
            if marker and marker.group(1)[0] == in_fence[0] and len(marker.group(1)) >= len(in_fence): in_fence = None
        elif marker:
            in_fence = marker.group(1); cleaned_lines.append("")
        else:
            cleaned_lines.append(line)
    return cleaned_lines


def headings(lines: list[str]):
    """Yield (index, depth, slug) for ATX and setext headings, numbering duplicate slugs like GitHub."""
    # Mask fenced blocks only: inline code is valid heading text and contributes its contents.
    lines = mask_fences(lines)
    used: set[str] = set()
    counts: dict[str, int] = {}
    i = 0
    while i < len(lines):
        line, index = lines[i], i
        h = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        setext = re.match(r"^\s{0,3}(=+|-+)\s*$", lines[i + 1]) if i + 1 < len(lines) else None
        if h:
            depth, title = len(h.group(1)), h.group(2)
        elif setext and line.strip():
            depth, title = (1 if setext.group(1)[0] == "=" else 2), line.strip()
            i += 1
        else:
            i += 1
            continue
        base = slugify(title)
        n = counts.get(base, 0)
        candidate = base if n == 0 else f"{base}-{n}"
        while candidate in used:
            n += 1; candidate = f"{base}-{n}"
        counts[base] = n + 1
        used.add(candidate)
        yield index, depth, candidate
        i += 1


def explicit_ids(line: str) -> list[str]:
    return re.findall(r'<a\s+(?:[^>]*\s)?id=["\']([^"\']+)', line, re.I)


def mask_code_lines(lines: list[str]) -> list[str]:
    """Blank fenced and inline code, keeping line indexes, so a quoted `<a id>` example is no anchor."""
    return mask_code("\n".join(lines)).split("\n")


def anchors(text: str) -> set[str]:
    lines = text.splitlines()
    found = {slug for _, _, slug in headings(lines)}
    for line in mask_code_lines(lines):
        found.update(explicit_ids(line))
    return found


def links(text: str):
    """Yield (line, destination) for inline, reference, and HTML links."""
    clean = mask_code(text)
    definitions = {}
    for i, line in enumerate(clean.splitlines(), 1):
        m = re.match(r"^\s{0,3}\[([^]]+)\]:\s*(?:<([^>]+)>|(\S+))", line)
        if m:
            definitions[m.group(1).strip().lower()] = (i, m.group(2) or m.group(3))
    for i, line in enumerate(clean.splitlines(), 1):
        if re.match(r"^\s{0,3}\[[^]]+\]:", line):
            continue
        for m in re.finditer(r"!?(?:\[[^]]*\])\((<[^>]+>|[^)]*)\)", line):
            destination = m.group(1).strip()
            if destination.startswith("<") and ">" in destination:
                destination = destination[1:destination.index(">")]
            else:
                # A quoted title may follow a destination; raw spaces in paths are allowed.
                title = re.search(r'\s+["\']', destination)
                if title:
                    destination = destination[:title.start()].rstrip()
            if destination:
                yield i, destination
        for m in re.finditer(r"(?<!!)\[([^]]+)\](?:\[([^]]*)\])?", line):
            key = (m.group(2) or m.group(1)).strip().lower()
            if key in definitions:
                yield i, definitions[key][1]
        for m in re.finditer(r"(?:href|src)=[\"']([^\"']+)[\"']", line, re.I):
            yield i, m.group(1)


def resolve_target(source: Path, target: str, repo: Path):
    """Resolve a local Markdown link; return (path, anchor), or (None, None)."""
    if target.startswith("//"):
        return None, None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None, None
    path = unquote(parsed.path)
    anchor = unquote(parsed.fragment)
    if path.startswith("/"):
        candidate = repo / path.lstrip("/")
    elif path:
        candidate = source.parent / path
    else:
        candidate = source
    candidate = candidate.resolve()
    return candidate, anchor
