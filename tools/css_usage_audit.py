#!/usr/bin/env python3
"""
CSS Usage Audit for Django project.
- Parses CSS selectors from twocomms_django_theme/static/css/styles.css
- Scans templates (.html), JS (.js), and Python (.py) for usage of class and id names
- Outputs a JSON report with potentially unused selectors and coverage stats

Safe: read-only. Does not modify project files.

Usage:
  python tools/css_usage_audit.py [--css PATH] [--root PATH] [--whitelist PATH]

Whitelist: optional newline-separated regexes to keep even if not found.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Reasonable selector regexes
CLASS_RE = re.compile(r"\.([a-zA-Z0-9_-]+)")
ID_RE = re.compile(r"#([a-zA-Z0-9_-]+)")
# Ignore utility pseudo-classes/elements and attribute selectors when extracting
IGNORE_IN_SELECTOR = re.compile(r":(hover|active|focus|focus-visible|focus-within|visited|disabled|root|before|after|first-child|last-child|nth-[^\s{]+)|\[[^\]]+\]")

# Patterns to ignore from search or treat as dynamic framework classes
DEFAULT_WHITELIST = [
    r"^swiper-", r"^toast-", r"^modal", r"^offcanvas", r"^collapse",
    r"^show$", r"^fade$", r"^active$", r"^disabled$", r"^open$",
    r"^is-", r"^has-", r"^js-", r"^aria-",
    r"^col-", r"^row$", r"^container$", r"^btn$", r"^btn-",
    r"^nav$", r"^navbar", r"^dropdown", r"^input-", r"^form-",
    r"^alert", r"^badge", r"^breadcrumb", r"^card", r"^table",
    r"^d-", r"^text-", r"^bg-", r"^mt-", r"^mb-", r"^ms-", r"^me-",
]

SEARCH_FILE_EXTS = {".html", ".htm", ".js", ".ts", ".py"}

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def read_file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_selectors(css_text: str) -> Tuple[Set[str], Set[str]]:
    css_text = CSS_COMMENT_RE.sub("", css_text)
    # Strip @media blocks etc. We only need raw selectors text
    # Rough split by '{' then take the selector part
    class_names: Set[str] = set()
    id_names: Set[str] = set()
    for block in css_text.split("{"):
        selector_part = block.split("}")[-1]  # keep last part minimal
        # Extract classes and ids from the selector header
        header = block.split("}")[0]
        header = header.strip()
        if not header or "@" in header:
            continue
        # Drop pseudo/attr parts for extraction safety
        cleaned = IGNORE_IN_SELECTOR.sub("", header)
        for m in CLASS_RE.finditer(cleaned):
            class_names.add(m.group(1))
        for m in ID_RE.finditer(cleaned):
            id_names.add(m.group(1))
    return class_names, id_names


def build_usage_corpus(root: Path) -> str:
    chunks: List[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in SEARCH_FILE_EXTS:
            # Skip minified vendor assets under staticfiles/admin etc.
            if "staticfiles/admin" in str(path):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            chunks.append(read_file_text(path))
    return "\n".join(chunks)


def compile_whitelist(whitelist_file: Path | None) -> List[re.Pattern]:
    patterns = list(DEFAULT_WHITELIST)
    if whitelist_file and whitelist_file.exists():
        extra = [line.strip() for line in whitelist_file.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.strip().startswith("#")]
        patterns.extend(extra)
    return [re.compile(p) for p in patterns]


def mark_used(selectors: Set[str], corpus: str, compiled_whitelist: List[re.Pattern]) -> Tuple[Set[str], Set[str]]:
    used: Set[str] = set()
    unused: Set[str] = set()
    # Fast path search by substring with word boundaries for robustness
    for name in selectors:
        keep = any(p.search(name) for p in compiled_whitelist)
        if keep:
            used.add(name)
            continue
        # Search as class="... name ..." or .name in JS or Python strings
        # Regex covers: class="...", 'class': '...', querySelector(.name), add/remove/toggle('name')
        pattern = re.compile(rf"(class(Name)?\\s*[=:]\\s*[\"']?[^\"']*\b{name}\b|[.#] ?{name}\b|addClass\(|removeClass\(|toggleClass\(|classList\.(add|remove|toggle)\(\s*[\"']{name}[\"'])",
                              re.IGNORECASE)
        if pattern.search(corpus):
            used.add(name)
        else:
            unused.add(name)
    return used, unused


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--css", default="twocomms/twocomms_django_theme/static/css/styles.css")
    parser.add_argument("--root", default=".")
    parser.add_argument("--whitelist", default="tools/css_whitelist.txt")
    parser.add_argument("--out", default="css_usage_report.json")
    args = parser.parse_args()

    css_path = Path(args.css).resolve()
    project_root = Path(args.root).resolve()
    whitelist_path = Path(args.whitelist).resolve()

    if not css_path.exists():
        print(f"CSS not found: {css_path}", file=sys.stderr)
        return 2

    css_text = read_file_text(css_path)
    class_names, id_names = extract_selectors(css_text)

    corpus = build_usage_corpus(project_root)
    wl = compile_whitelist(whitelist_path if whitelist_path.exists() else None)

    used_classes, unused_classes = mark_used(class_names, corpus, wl)
    used_ids, unused_ids = mark_used(id_names, corpus, wl)

    report: Dict[str, object] = {
        "css_path": str(css_path),
        "project_root": str(project_root),
        "totals": {
            "classes": len(class_names),
            "ids": len(id_names),
        },
        "usage": {
            "classes_used": len(used_classes),
            "classes_unused": len(unused_classes),
            "ids_used": len(used_ids),
            "ids_unused": len(unused_ids),
        },
        "unused": {
            "classes": sorted(unused_classes),
            "ids": sorted(unused_ids),
        },
    }

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary
    print(f"CSS selectors: classes={len(class_names)}, ids={len(id_names)}")
    print(f"Unused: classes={len(unused_classes)}, ids={len(unused_ids)}")
    top_preview = sorted(list(unused_classes))[:40]
    if top_preview:
        print("Sample unused classes (first 40):")
        for name in top_preview:
            print(" -", name)
    print(f"Full report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
