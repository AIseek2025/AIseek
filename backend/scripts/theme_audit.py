import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


CSS_SUSPECT_SELECTORS = (
    "p-tab",
    "tab-item",
    "settings",
    "search",
    "inbox",
    "creator",
    "profile",
    "friends",
    "following",
    "modal",
)


def read_text(p: Path) -> str:
    try:
        return p.read_text("utf-8", errors="ignore")
    except Exception:
        return ""


def find_matches(text: str, pat: re.Pattern) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in pat.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        snippet = text[m.start() : min(len(text), m.end() + 80)].splitlines()[0]
        out.append((line_no, snippet.strip()))
    return out


def main() -> int:
    idx = ROOT / "backend" / "templates" / "index.html"
    if not idx.exists():
        print("index.html not found")
        return 2

    text = read_text(idx)

    selector_union = "|".join(re.escape(s) for s in CSS_SUSPECT_SELECTORS)
    css_white = re.compile(
        rf"\.({selector_union})[^\{{]*\{{[^}}]*color\s*:\s*white\b",
        re.IGNORECASE | re.DOTALL,
    )
    inline_white = re.compile(r'style\s*=\s*"[^"]*color\s*:\s*white\b', re.IGNORECASE)

    bad = []
    bad += [("css", *x) for x in find_matches(text, css_white)]
    bad += [("inline", *x) for x in find_matches(text, inline_white)]

    if bad:
        print("THEME_AUDIT_FAIL")
        for kind, line, snippet in bad[:200]:
            print(f"- {kind} line {line}: {snippet}")
        return 1

    print("THEME_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
