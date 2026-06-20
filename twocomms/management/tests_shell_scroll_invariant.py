"""Регресійний інваріант скролу management-оболонки.

Контекст: історично «не доскролити низ» виникало на нових сторінках, бо
оболонка покладалася на `calc(100vh - offset)` із magic-number висоти хедера.
Глобальний фікс (commit f793d8c6) перевів оболонку на grid `auto / 1fr` із
єдиним внутрішнім скрол-контейнером `.content-area`. Цей тест кодифікує
інваріант, щоб правка CSS не могла мовчки його зламати знову.

Тест читає вихідний `management.css` і перевіряє ключові декларації. Він НЕ
запускає браузер — перевіряється сама механіка скролу на рівні CSS-правил
(саме її зняття і повертало баг).
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS_PATH = Path(settings.BASE_DIR) / "twocomms_django_theme" / "static" / "css" / "management.css"


def _strip_comments(css: str) -> str:
    # CSS-коментарі можуть містити `{` / `}` (напр. body{overflow:hidden}),
    # що ламає наївний парс правил — прибираємо їх повністю.
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _read_css() -> str:
    return _strip_comments(CSS_PATH.read_text(encoding="utf-8"))


def _media_blocks(css: str, query_re: str) -> list[str]:
    """Усі тіла @media-блоків, що матчать query (через підрахунок дужок)."""
    blocks = []
    for m in re.finditer(r"@media[^{]*" + query_re + r"[^{]*\{", css):
        start = m.end()
        depth = 1
        i = start
        while i < len(css) and depth > 0:
            ch = css[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        blocks.append(css[start : i - 1])
    return blocks


def _rule_bodies(css: str, selector: str) -> list[str]:
    """Повертає тіла всіх правил, чий селектор ТОЧНО дорівнює `selector`.

    Виключає похідні (`.management-body::after`, `.management-body.modal-open`,
    `.management-body[data-...]`), бо перед `{` має йти лише пробіли.
    """
    pattern = re.compile(
        r"(?<![\w\-.#\[:])" + re.escape(selector) + r"\s*\{([^}]*)\}"
    )
    return [m.group(1) for m in pattern.finditer(css)]


def _normalize(block: str) -> str:
    # прибираємо пробіли навколо `:` і `;`, схлопуємо пробіли, нижній регістр
    block = re.sub(r"\s*([:;{},])\s*", r"\1", block)
    block = re.sub(r"\s+", " ", block)
    return block.lower()


class ShellScrollInvariantTests(SimpleTestCase):
    """Гарантує, що грид-оболонка зі скролом у .content-area не регресує."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = _read_css()

    def test_css_file_exists(self):
        self.assertTrue(CSS_PATH.exists(), f"management.css не знайдено: {CSS_PATH}")

    def test_management_body_is_full_height_grid(self):
        bodies = [_normalize(b) for b in _rule_bodies(self.css, ".management-body")]
        self.assertTrue(bodies, "Не знайдено базового правила .management-body")
        grid_body = next(
            (b for b in bodies if "display:grid" in b),
            None,
        )
        self.assertIsNotNone(
            grid_body,
            "Оболонка .management-body має бути display:grid (інваріант скролу).",
        )
        # Висота на весь вьюпорт + 2 рядки (хедер auto + робоча область 1fr).
        self.assertIn("height:100vh", grid_body)
        self.assertIn("grid-template-rows:auto 1fr", grid_body)
        # body не скролиться сам — скрол лише у .content-area.
        self.assertIn("overflow:hidden", grid_body)

    def test_content_area_is_the_single_scroll_container(self):
        bodies = [_normalize(b) for b in _rule_bodies(self.css, ".content-area")]
        self.assertTrue(bodies, "Не знайдено правила .content-area")
        scroll_body = next((b for b in bodies if "overflow-y:auto" in b), None)
        self.assertIsNotNone(
            scroll_body,
            ".content-area має бути єдиним скрол-контейнером (overflow-y:auto).",
        )
        # height:100% бере висоту з робочого рядка grid (без calc/magic-number).
        self.assertIn("height:100%", scroll_body)
        # padding має входити у висоту, інакше низ ховається під body{overflow:hidden}.
        self.assertIn("box-sizing:border-box", scroll_body)

    def test_mobile_breakpoint_restores_document_flow(self):
        # На вузьких екранах оболонка повертається у звичайний потік (body скролиться).
        blocks = _media_blocks(self.css, r"max-width:\s*1080px")
        self.assertTrue(blocks, "Не знайдено мобільний брейкпойнт max-width:1080px")
        mobile_bodies = []
        for blk in blocks:
            mobile_bodies.extend(_normalize(b) for b in _rule_bodies(blk, ".management-body"))
        self.assertTrue(mobile_bodies, "У мобільному медіа немає правила .management-body")
        restored = next(
            (b for b in mobile_bodies if "overflow:auto" in b or "height:auto" in b),
            None,
        )
        self.assertIsNotNone(
            restored,
            "На ≤1080px .management-body має повертати потік (height:auto/overflow:auto).",
        )

    def test_no_magic_number_calc_offset_in_shell(self):
        # Заборонений старий band-aid: calc(100vh - <header offset>) на оболонці.
        # Він повертав баг, коли реальна висота хедера != magic-number.
        norm = _normalize(self.css)
        # Дозволяємо calc у модалках/попаперах (max-height), але НЕ height: calc(100vh-..)
        forbidden = re.search(r"height:calc\(100vh-\d+px\)", norm)
        self.assertIsNone(
            forbidden,
            "Знайдено заборонений per-page band-aid height:calc(100vh - Npx) — "
            "оболонка має покладатися на grid 1fr, не на magic-number висоти хедера.",
        )
