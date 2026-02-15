from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rcssmin import cssmin
from rjsmin import jsmin


@dataclass(frozen=True)
class MinifyTarget:
    source: Path
    output: Path
    kind: str  # "css" | "js"


@dataclass
class MinifyResult:
    source: Path
    output: Path
    written: bool
    source_size: int
    output_size: int


def _dtf_targets(base_dir: Path) -> list[MinifyTarget]:
    dtf_static = base_dir / "dtf" / "static" / "dtf"
    return [
        MinifyTarget(
            source=dtf_static / "css" / "dtf.css",
            output=dtf_static / "css" / "dtf.min.css",
            kind="css",
        ),
        MinifyTarget(
            source=dtf_static / "js" / "dtf.js",
            output=dtf_static / "js" / "dtf.min.js",
            kind="js",
        ),
        MinifyTarget(
            source=dtf_static / "js" / "components" / "effects-bundle.js",
            output=dtf_static / "js" / "components" / "effects-bundle.min.js",
            kind="js",
        ),
    ]


def _minify_content(source_text: str, kind: str) -> str:
    if kind == "css":
        return cssmin(source_text)
    if kind == "js":
        return jsmin(source_text)
    raise ValueError(f"Unsupported minification kind: {kind}")


def build_dtf_minified_assets(base_dir: Path) -> list[MinifyResult]:
    results: list[MinifyResult] = []
    for target in _dtf_targets(base_dir):
        if not target.source.exists():
            raise FileNotFoundError(f"Source asset not found: {target.source}")

        source_text = target.source.read_text(encoding="utf-8")
        minified = _minify_content(source_text, target.kind).strip()
        if minified:
            minified += "\n"

        previous = None
        if target.output.exists():
            previous = target.output.read_text(encoding="utf-8")

        written = previous != minified
        if written:
            target.output.parent.mkdir(parents=True, exist_ok=True)
            target.output.write_text(minified, encoding="utf-8")

        results.append(
            MinifyResult(
                source=target.source,
                output=target.output,
                written=written,
                source_size=len(source_text.encode("utf-8")),
                output_size=len(minified.encode("utf-8")),
            )
        )
    return results


def summarize_minify_results(results: Iterable[MinifyResult]) -> dict[str, int]:
    src_total = 0
    out_total = 0
    written = 0
    count = 0
    for item in results:
        count += 1
        src_total += item.source_size
        out_total += item.output_size
        if item.written:
            written += 1
    return {
        "files_total": count,
        "files_written": written,
        "source_bytes": src_total,
        "output_bytes": out_total,
        "saved_bytes": max(0, src_total - out_total),
    }
