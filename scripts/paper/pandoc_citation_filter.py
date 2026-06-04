#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from pandocfilters import Para, Space, Str, stringify, toJSONFilter


BRACED_UMLAUT_PATTERN = re.compile(r'\{"([A-Za-z])\}')
BACKSLASH_UMLAUT_PATTERN = re.compile(r'\\"([A-Za-z])')
AUTHOR_PLACEHOLDERS = {"others", "et al", "et al."}
MAX_REFERENCE_AUTHORS = 8
STATE: "FilterState | None" = None


@dataclass
class BibEntry:
    key: str
    fields: Dict[str, str]

    @property
    def year(self) -> str:
        return clean_text(self.fields.get("year", "n.d."))

    @property
    def author_label(self) -> str:
        authors = split_authors(self.fields.get("author", ""))
        if not authors:
            return self.key
        first = authors[0]
        if len(authors) == 1 and not has_additional_authors(self.fields.get("author", "")):
            return first
        return f"{first} et al."

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (
            self.author_label.lower(),
            self.year,
            clean_text(self.fields.get("title", "")).lower(),
        )


@dataclass
class FilterState:
    entries: Dict[str, BibEntry]
    cited_keys: List[str] = field(default_factory=list)

    def note_citation(self, key: str) -> None:
        if key not in self.entries:
            raise RuntimeError(f"Missing bibliography key: {key}")
        if key not in self.cited_keys:
            self.cited_keys.append(key)


def clean_text(value: str) -> str:
    text = value.strip()
    text = text.replace(r"\&", "&")
    text = text.replace("--", "-")
    text = BRACED_UMLAUT_PATTERN.sub(lambda match: match.group(1), text)
    text = BACKSLASH_UMLAUT_PATTERN.sub(lambda match: match.group(1), text)
    replacements = {
        r'\"a': "a",
        r'\"o': "o",
        r'\"u': "u",
        r'\"A': "A",
        r'\"O': "O",
        r'\"U': "U",
        r"\'": "",
        r"\`": "",
        r"\^": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().strip(",")


def parse_author_names(raw: str) -> Tuple[List[str], bool]:
    authors: List[str] = []
    placeholder_seen = False
    for part in raw.split(" and "):
        author = clean_text(part).strip()
        if not author:
            continue
        if author.lower() in AUTHOR_PLACEHOLDERS:
            placeholder_seen = True
            continue
        authors.append(author)
    return authors, placeholder_seen


def has_additional_authors(raw: str) -> bool:
    authors, placeholder_seen = parse_author_names(raw)
    return placeholder_seen or len(authors) > 1


def split_authors(raw: str) -> List[str]:
    parsed_authors, _ = parse_author_names(raw)
    authors: List[str] = []
    for author in parsed_authors:
        if "," in author:
            surname = author.split(",", 1)[0].strip()
        else:
            tokens = author.split()
            surname = author if len(tokens) == 1 else tokens[-1]
            if author.lower().endswith("consortium"):
                surname = author
        authors.append(surname)
    return authors


def format_author_names(raw: str, *, max_authors: int = MAX_REFERENCE_AUTHORS) -> str:
    authors, placeholder_seen = parse_author_names(raw)
    if not authors:
        return ""
    display_authors = authors[:max_authors]
    formatted = ", ".join(display_authors)
    if placeholder_seen or len(authors) > max_authors:
        return f"{formatted}, et al."
    return formatted


def parse_bibtex(path: Path) -> Dict[str, BibEntry]:
    text = path.read_text(encoding="utf-8")
    entries: Dict[str, BibEntry] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("@"):
            i += 1
            continue
        match = re.match(r"@(\w+)\{([^,]+),", line)
        if not match:
            i += 1
            continue
        key = match.group(2)
        fields: Dict[str, str] = {}
        i += 1
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "}":
                break
            if not stripped or "=" not in stripped:
                i += 1
                continue
            name, value = stripped.split("=", 1)
            name = name.strip().lower()
            value = value.strip().rstrip(",")
            brace_delta = value.count("{") - value.count("}")
            while brace_delta > 0 and i + 1 < len(lines):
                i += 1
                extra = lines[i].strip().rstrip(",")
                value += " " + extra
                brace_delta = value.count("{") - value.count("}")
            if value.startswith("{") and value.endswith("}"):
                value = value[1:-1]
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            fields[name] = value
            i += 1
        entries[key] = BibEntry(key=key, fields=fields)
        i += 1
    return entries


def format_inline_citation(entry: BibEntry) -> str:
    return f"{entry.author_label}, {entry.year}"


def format_reference(entry: BibEntry) -> str:
    authors = format_author_names(entry.fields.get("author", entry.key)) or entry.key
    title = clean_text(entry.fields.get("title", "Untitled"))
    journal = clean_text(entry.fields.get("journal", ""))
    volume = clean_text(entry.fields.get("volume", ""))
    number = clean_text(entry.fields.get("number", ""))
    pages = clean_text(entry.fields.get("pages", ""))
    doi = clean_text(entry.fields.get("doi", ""))
    url = clean_text(entry.fields.get("url", ""))

    parts: List[str] = [f"{authors} ({entry.year}). {title}."]
    if journal:
        if volume and number:
            parts.append(f"{journal} {volume}({number}).")
        elif volume:
            parts.append(f"{journal} {volume}.")
        else:
            parts.append(f"{journal}.")
    if pages:
        parts.append(f"pp. {pages}.")
    if doi:
        doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        parts.append(doi_url)
    elif url:
        parts.append(url)
    return " ".join(part for part in parts if part)


def render_references(keys: Iterable[str], entries: Dict[str, BibEntry]) -> str:
    unique_keys = sorted(set(keys), key=lambda key: entries[key].sort_key)
    return "\n\n".join(format_reference(entries[key]) for key in unique_keys)


def text_to_inlines(text: str):
    tokens = text.split()
    inlines = []
    for index, token in enumerate(tokens):
        if index:
            inlines.append(Space())
        inlines.append(Str(token))
    return inlines


def meta_to_text(meta_value):
    if meta_value is None:
        return ""
    kind = meta_value["t"]
    content = meta_value["c"]
    if kind == "MetaString":
        return content
    if kind in {"MetaInlines", "MetaBlocks"}:
        return stringify(content)
    if kind == "MetaList":
        return [meta_to_text(item) for item in content]
    return ""


def resolve_bibliography_path(meta) -> Path:
    bibliography = meta.get("bibliography")
    raw_value = meta_to_text(bibliography)
    if isinstance(raw_value, list):
        raw_value = raw_value[0]
    if not raw_value:
        raise RuntimeError("manuscript metadata is missing bibliography")
    path = Path(raw_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def load_state(meta) -> FilterState:
    global STATE
    if STATE is None:
        bib_path = resolve_bibliography_path(meta)
        STATE = FilterState(entries=parse_bibtex(bib_path))
    return STATE


def action(key, value, _format, meta):
    state = load_state(meta)

    if key == "Cite":
        citations, _inlines = value
        rendered: List[str] = []
        for citation in citations:
            citation_id = citation["citationId"]
            state.note_citation(citation_id)
            rendered.append(format_inline_citation(state.entries[citation_id]))
        return text_to_inlines(f"({'; '.join(rendered)})")

    if key == "Div":
        [[identifier, _classes, _attrs], _blocks] = value
        if identifier == "refs":
            reference_keys = sorted(set(state.cited_keys), key=lambda key: state.entries[key].sort_key)
            return [Para(text_to_inlines(format_reference(state.entries[key]))) for key in reference_keys]

    return None


def main() -> None:
    toJSONFilter(action)


if __name__ == "__main__":
    main()
