#!/usr/bin/env python3
"""Tech debt inventory — собирает данные для 05_tech_debt.md.

Запускать из корня проекта.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/Users/zainllw0w/TwoComms/site')
OUT_DIR = ROOT / '.kiro/specs/seo-molecular-upgrade/audit/audit_data'
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules', '.kiro',
    'dtf', 'tmp', 'staticfiles', '.tmp_linking',
    'BrandDNA', 'SEO', 'docs', 'output',
    'analysis_reports_20251024_190327', 'newCatalog', 'opros',
    'codex_skills', 'Anl', 'Ideas', 'infra', 'listicle-generator-package',
    'Logo_fire', 'problems', 'specs', 'tests', 'test-results', 'SEOScreen',
    'artifacts', 'twocomms_django_theme.media', 'media',
}

# Специальные исключения для twocomms/twocomms/...
INCLUDE_ROOTS = [
    ROOT / 'twocomms/storefront',
    ROOT / 'twocomms/twocomms_django_theme/templates',
    ROOT / 'twocomms/twocomms',
    ROOT / 'twocomms/static',
    ROOT / 'twocomms/accounts',
    ROOT / 'twocomms/orders',
    ROOT / 'twocomms/reviews',
    ROOT / 'twocomms/productcolors',
    ROOT / 'twocomms/surveys',
    ROOT / 'twocomms/main',
    ROOT / 'twocomms/management',
    ROOT / 'twocomms/warehouse',
]


def walk_files(root: Path, suffixes: tuple[str, ...]):
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        # exclude dirs by path
        parts = set(p.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if p.suffix in suffixes:
            yield p


def collect_template_comments():
    out = {
        'multiline_consecutive_runs': [],
        'phase_comments_total': 0,
        'phase_ids': Counter(),
        'comment_count_per_file': Counter(),
        'total_django_comments': 0,
    }
    templates_dir = ROOT / 'twocomms/twocomms_django_theme/templates'
    for path in walk_files(templates_dir, ('.html',)):
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        run_start = None
        run_count = 0
        for i, ln in enumerate(lines, start=1):
            stripped = ln.strip()
            if stripped.startswith('{#') and stripped.endswith('#}'):
                out['comment_count_per_file'][rel] += 1
                out['total_django_comments'] += 1
                if run_start is None:
                    run_start = i
                    run_count = 1
                else:
                    run_count += 1
                m = re.search(r'Phase\s+(\d+[a-z]?)', stripped)
                if m:
                    out['phase_comments_total'] += 1
                    out['phase_ids'][m.group(1)] += 1
            else:
                if run_start is not None and run_count >= 3:
                    out['multiline_consecutive_runs'].append({
                        'path': rel,
                        'start': run_start,
                        'end': run_start + run_count - 1,
                        'count': run_count,
                        'sample': '\n'.join(lines[run_start - 1:run_start + run_count - 1])[:400],
                    })
                run_start = None
                run_count = 0
        if run_start is not None and run_count >= 3:
            out['multiline_consecutive_runs'].append({
                'path': rel,
                'start': run_start,
                'end': run_start + run_count - 1,
                'count': run_count,
                'sample': '\n'.join(lines[run_start - 1:run_start + run_count - 1])[:400],
            })
    return out


def collect_python_phase_comments():
    out = {
        'phase_comments_total': 0,
        'phase_ids': Counter(),
        'phase_comments_per_file': Counter(),
    }
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for path in walk_files(include, ('.py',)):
            rel = str(path.relative_to(ROOT))
            try:
                content = path.read_text(encoding='utf-8')
            except Exception:
                continue
            for m in re.finditer(r'Phase\s+(\d+[a-z]?)', content):
                out['phase_comments_total'] += 1
                out['phase_ids'][m.group(1)] += 1
                out['phase_comments_per_file'][rel] += 1
    return out


def collect_todo_fixme():
    """TODO/FIXME/XXX/HACK/DEPRECATED in python (по include-rootам)."""
    out = []
    pat = re.compile(r'#\s*(TODO|FIXME|XXX|HACK|DEPRECATED|OLD)\b', re.IGNORECASE)
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for path in walk_files(include, ('.py',)):
            rel = str(path.relative_to(ROOT))
            try:
                lines = path.read_text(encoding='utf-8').splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines, start=1):
                m = pat.search(ln)
                if m:
                    out.append({
                        'path': rel,
                        'line': i,
                        'tag': m.group(1).upper(),
                        'text': ln.strip()[:200],
                    })
    return out


def collect_unused_imports():
    """Поиск потенциально неиспользуемых imports.

    Грубая эвристика — учитываем только если:
    - в строке нет `# noqa` (re-export или intentional)
    - имя не *, не F-код, не присутствует в `__all__`
    - файл не `__init__.py` (re-exports)
    - имя реально не упоминается в файле
    """
    findings = []
    import_pat = re.compile(r'^(?:from\s+\S+\s+import\s+(.+)|import\s+(.+))$')
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for path in walk_files(include, ('.py',)):
            rel = str(path.relative_to(ROOT))
            if path.name == '__init__.py':
                # __init__.py — почти всегда re-exports; пропускаем
                continue
            try:
                lines = path.read_text(encoding='utf-8').splitlines()
                content = '\n'.join(lines)
            except Exception:
                continue
            # parse imports (handle multi-line via simple paren joining)
            joined_lines = []
            buffer = ''
            buf_start = 0
            in_paren = False
            for i, ln in enumerate(lines, start=1):
                stripped = ln.rstrip('\\').rstrip()
                if in_paren:
                    buffer += ' ' + stripped
                    if ')' in stripped:
                        in_paren = False
                        joined_lines.append((buf_start, buffer.strip()))
                        buffer = ''
                    continue
                if re.match(r'^\s*(from\s+\S+\s+import\s+\(|import\s+\()', ln):
                    if ')' in ln:
                        joined_lines.append((i, ln.strip()))
                    else:
                        in_paren = True
                        buffer = ln.strip()
                        buf_start = i
                else:
                    if 'import' in ln and re.match(r'^\s*(from\s+\S+\s+import\s+|import\s+)', ln):
                        joined_lines.append((i, ln.strip()))
            local_imports = []
            for line_no, raw in joined_lines:
                if 'noqa' in raw.lower():
                    continue
                m = import_pat.match(raw)
                if not m:
                    continue
                names = m.group(1) or m.group(2)
                if not names:
                    continue
                clean = re.sub(r'[()]', '', names)
                for tok in clean.split(','):
                    tok = tok.strip()
                    if not tok or tok == '*':
                        continue
                    if ' as ' in tok:
                        name = tok.split(' as ')[1].strip()
                    else:
                        name = tok.split('.')[0].strip()
                    if not re.match(r'^[A-Za-z_][\w]*$', name):
                        continue
                    if name.startswith('_'):
                        continue
                    local_imports.append((name, line_no, raw))
            # check usage
            all_match = re.search(r"__all__\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
            all_names = set()
            if all_match:
                for q in re.findall(r"['\"]([\w_]+)['\"]", all_match.group(1)):
                    all_names.add(q)
            for name, line, raw in local_imports:
                if name in all_names:
                    continue
                pat = re.compile(r'\b' + re.escape(name) + r'\b')
                cnt_total = len(pat.findall(content))
                # count occurrences within the import statement only
                cnt_imp = len(pat.findall(raw))
                if cnt_total - cnt_imp == 0 and name not in ('annotations',):
                    findings.append({
                        'path': rel,
                        'line': line,
                        'name': name,
                        'raw': raw[:160],
                    })
    return findings


def collect_view_functions():
    """Все view-функции в storefront/views/*.py."""
    out = []
    views_dir = ROOT / 'twocomms/storefront/views'
    for path in walk_files(views_dir, ('.py',)):
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, start=1):
            m = re.match(r'^def\s+([a-zA-Z_]\w*)\s*\(', ln)
            if m:
                name = m.group(1)
                if name.startswith('_'):
                    continue
                out.append({'path': rel, 'line': i, 'name': name})
    return out


def collect_url_names():
    """Парсим urls.py / api_urls.py — собираем все name=..."""
    out = []
    paths = [
        ROOT / 'twocomms/twocomms/urls.py',
        ROOT / 'twocomms/twocomms/urls_dtf.py',
        ROOT / 'twocomms/twocomms/urls_management.py',
        ROOT / 'twocomms/twocomms/urls_storage.py',
        ROOT / 'twocomms/storefront/urls.py',
        ROOT / 'twocomms/storefront/api_urls.py',
        ROOT / 'twocomms/accounts/urls.py' if (ROOT / 'twocomms/accounts/urls.py').exists() else None,
        ROOT / 'twocomms/orders/urls.py' if (ROOT / 'twocomms/orders/urls.py').exists() else None,
        ROOT / 'twocomms/reviews/urls.py' if (ROOT / 'twocomms/reviews/urls.py').exists() else None,
        ROOT / 'twocomms/main/urls.py' if (ROOT / 'twocomms/main/urls.py').exists() else None,
    ]
    for path in paths:
        if path is None or not path.exists():
            continue
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, start=1):
            m = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', ln)
            if m:
                # try to find the view name
                vmatch = re.search(r'(?:path|re_path|url)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*([\w\.]+)', ln)
                view = vmatch.group(1) if vmatch else ''
                out.append({
                    'path': rel,
                    'line': i,
                    'name': m.group(1),
                    'view': view,
                    'raw': ln.strip()[:200],
                })
    return out


def collect_template_url_names():
    """Все {% url 'name' %} в шаблонах."""
    used_names = Counter()
    templates_dir = ROOT / 'twocomms/twocomms_django_theme/templates'
    for path in walk_files(templates_dir, ('.html',)):
        try:
            content = path.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in re.finditer(r"\{%\s*url\s*['\"]([^'\"]+)['\"]", content):
            used_names[m.group(1)] += 1
    return dict(used_names)


def collect_python_url_names():
    """reverse('name') и redirect('name', ...) в python."""
    used = Counter()
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for path in walk_files(include, ('.py',)):
            try:
                content = path.read_text(encoding='utf-8')
            except Exception:
                continue
            for m in re.finditer(r"(?:reverse|reverse_lazy|redirect)\s*\(\s*['\"]([\w\-_:]+)['\"]", content):
                used[m.group(1)] += 1
    return dict(used)


def collect_css_files():
    out = []
    for base in [ROOT / 'twocomms/static/css', ROOT / 'twocomms/twocomms_django_theme/static/css']:
        if not base.exists():
            continue
        for path in walk_files(base, ('.css',)):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            out.append({'path': str(path.relative_to(ROOT)), 'size': size})
    out.sort(key=lambda x: -x['size'])
    return out


def collect_js_files():
    out = []
    for base in [ROOT / 'twocomms/static/js', ROOT / 'twocomms/twocomms_django_theme/static/js']:
        if not base.exists():
            continue
        for path in walk_files(base, ('.js',)):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            out.append({'path': str(path.relative_to(ROOT)), 'size': size})
    out.sort(key=lambda x: -x['size'])
    return out


def collect_template_sizes():
    out = []
    templates_dir = ROOT / 'twocomms/twocomms_django_theme/templates'
    for path in walk_files(templates_dir, ('.html',)):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        out.append({'path': str(path.relative_to(ROOT)), 'size': size})
    out.sort(key=lambda x: -x['size'])
    return out


def collect_template_renders():
    """Find render(request, 'pages/x.html', ...) and template_name = ..."""
    used = Counter()
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for path in walk_files(include, ('.py',)):
            try:
                content = path.read_text(encoding='utf-8')
            except Exception:
                continue
            for m in re.finditer(r"render\s*\(\s*[\w_]+\s*,\s*['\"]([^'\"]+\.html)['\"]", content):
                used[m.group(1)] += 1
            for m in re.finditer(r"template_name\s*=\s*['\"]([^'\"]+\.html)['\"]", content):
                used[m.group(1)] += 1
            for m in re.finditer(r"get_template\s*\(\s*['\"]([^'\"]+\.html)['\"]", content):
                used[m.group(1)] += 1
            for m in re.finditer(r"render_to_string\s*\(\s*['\"]([^'\"]+\.html)['\"]", content):
                used[m.group(1)] += 1
    return dict(used)


def collect_template_includes():
    """{% include 'x.html' %} and {% extends 'x.html' %} в шаблонах."""
    used = Counter()
    templates_dir = ROOT / 'twocomms/twocomms_django_theme/templates'
    for path in walk_files(templates_dir, ('.html',)):
        try:
            content = path.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in re.finditer(r"\{%\s*(?:include|extends)\s+['\"]([^'\"]+\.html)['\"]", content):
            used[m.group(1)] += 1
    return dict(used)


def collect_runpython_migrations():
    out = []
    for include in INCLUDE_ROOTS:
        if not include.exists():
            continue
        for migdir in include.rglob('migrations'):
            if not migdir.is_dir():
                continue
            for path in walk_files(migdir, ('.py',)):
                try:
                    content = path.read_text(encoding='utf-8')
                except Exception:
                    continue
                if 'RunPython' in content:
                    rel = str(path.relative_to(ROOT))
                    # Extract first lines context
                    lines = content.splitlines()
                    first_runpython = None
                    for i, ln in enumerate(lines, start=1):
                        if 'RunPython' in ln:
                            first_runpython = i
                            break
                    out.append({
                        'path': rel,
                        'first_runpython_line': first_runpython,
                        'size_bytes': len(content),
                    })
    return out


def main():
    data = {}
    print('Step 1/12: template comments...', file=sys.stderr)
    data['template_comments'] = collect_template_comments()
    print('Step 2/12: python phase comments...', file=sys.stderr)
    data['python_phase_comments'] = collect_python_phase_comments()
    print('Step 3/12: TODO/FIXME...', file=sys.stderr)
    data['todo_fixme'] = collect_todo_fixme()
    print('Step 4/12: unused imports...', file=sys.stderr)
    data['unused_imports'] = collect_unused_imports()
    print('Step 5/12: view functions...', file=sys.stderr)
    data['view_functions'] = collect_view_functions()
    print('Step 6/12: url names...', file=sys.stderr)
    data['url_names'] = collect_url_names()
    print('Step 7/12: template url usage...', file=sys.stderr)
    data['template_url_usage'] = collect_template_url_names()
    print('Step 8/12: python url usage...', file=sys.stderr)
    data['python_url_usage'] = collect_python_url_names()
    print('Step 9/12: css/js/templates sizes...', file=sys.stderr)
    data['css_files'] = collect_css_files()
    data['js_files'] = collect_js_files()
    data['template_sizes'] = collect_template_sizes()
    print('Step 10/12: template renders...', file=sys.stderr)
    data['template_renders'] = collect_template_renders()
    data['template_includes'] = collect_template_includes()
    print('Step 11/12: migrations runpython...', file=sys.stderr)
    data['runpython_migrations'] = collect_runpython_migrations()
    print('Step 12/12: writing output...', file=sys.stderr)

    # Counters → dict
    def counters_to_dict(obj):
        if isinstance(obj, dict):
            return {k: counters_to_dict(v) for k, v in obj.items()}
        if isinstance(obj, Counter):
            return dict(obj)
        if isinstance(obj, list):
            return [counters_to_dict(x) for x in obj]
        return obj
    data = counters_to_dict(data)

    out_path = OUT_DIR / '05_tech_debt_raw.json'
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote: {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
