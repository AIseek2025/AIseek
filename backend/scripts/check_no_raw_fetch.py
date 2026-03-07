import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRS = [
    ROOT / "backend" / "static" / "js" / "app",
    ROOT / "backend" / "static" / "js" / "modules",
]

ALLOW_FILES = {
    ROOT / "backend" / "static" / "js" / "app" / "api.js",
    ROOT / "backend" / "static" / "js" / "app" / "studio.js",
    ROOT / "backend" / "static" / "js" / "modules" / "runtime.js",
}


RE_ANY_FETCH = re.compile(r"\bfetch\s*\(", re.MULTILINE)


def line_no(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def main() -> int:
    violations: list[tuple[str, int, str]] = []

    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.js"):
            if p in ALLOW_FILES:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for m in RE_ANY_FETCH.finditer(txt):
                ln = line_no(txt, m.start())
                try:
                    line = txt.splitlines()[ln - 1].strip()
                except Exception:
                    line = "fetch("
                violations.append((str(p.relative_to(ROOT)), ln, line[:260]))

    if violations:
        sys.stdout.write("RAW_FETCH_FOUND\n")
        for fp, ln, line in violations[:200]:
            sys.stdout.write(f"- {fp}:{ln}: {line}\n")
        sys.stdout.write("Do not call fetch() directly. Use app.apiRequest/app.apiGetJSON/app.apiPostJSON/app.apiBeacon.\n")
        return 1

    sys.stdout.write("OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
