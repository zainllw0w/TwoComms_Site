#!/usr/bin/env python3
"""Поиск источника каждой top-фразы в кодовой базе.

Грепаем по storefront/, twocomms_django_theme/templates/, locale/.
"""
import json, os, re, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # twocomms/
summary = json.load(open(os.path.join(HERE, "summary.json"), encoding="utf-8"))


SEARCH_DIRS = [
    "storefront",
    "twocomms_django_theme/templates",
    "locale",
    "main",
    "twocomms",
]

def grep_phrase(phrase: str, max_matches: int = 5) -> list[str]:
    # Очень короткие фразы (<6 chars) пропускаем — слишком шумно.
    if len(phrase.strip()) < 6:
        return []
    # Используем фрагмент длиной до 60 символов, чтобы не натыкаться на
    # длинные шаблонные строки.
    needle = phrase[:60].strip()
    # Для grep избавляемся от спецсимволов.
    out = []
    for d in SEARCH_DIRS:
        path = os.path.join(ROOT, d)
        if not os.path.exists(path):
            continue
        try:
            r = subprocess.run(
                ["/usr/bin/grep", "-Rn", "--include=*.py", "--include=*.html",
                 "--include=*.po", "--include=*.json", "-F", needle, path],
                capture_output=True, text=True, timeout=20,
            )
            for line in r.stdout.splitlines()[:max_matches]:
                # отрезаем root, чтобы пути были короче.
                if line.startswith(ROOT):
                    line = line[len(ROOT) + 1:]
                out.append(line)
                if len(out) >= max_matches:
                    return out
        except Exception:
            pass
    return out


# Ищем top-30 фраз
clusters = summary["phrase_clusters"][:30]
result = []
for c in clusters:
    p = c["phrase"]
    refs = grep_phrase(p)
    result.append({
        "phrase": p,
        "count": c["count"],
        "examples": c["examples"][:3],
        "source_refs": refs,
    })
    print(f"{c['count']:3d}× {p[:60]}{'…' if len(p)>60 else ''}")
    for ref in refs[:3]:
        print("    src:", ref)
    print()
json.dump(result, open(os.path.join(HERE, "source_trace.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"-> _audit/source_trace.json ({len(result)} clusters)")
