"""Іконки-«картки» рахунків: пресети банків/емодзі, обробка завантаженого
фото у легкий WEBP та рендер прямокутної картки-іконки.

Іконка робить рахунки візуально розрізнюваними у боковому меню та списку
керування. Підтримуються чотири режими (Account.ICON_*): без іконки, емодзі,
брендова плитка банку та власне зображення (зберігається як стиснутий
WEBP data-URI — важкий оригінал відкидається одразу після переформатування).
"""
from __future__ import annotations

import base64
import io

from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

# Цільовий розмір картки-іконки (співвідношення ~1.6 як у банківської картки).
# Рендеримо у 2× для чіткості на retina; на екрані ~34×21.
ICON_PX = (112, 70)
ICON_MAX_UPLOAD = 8 * 1024 * 1024  # 8 МБ на вихідний файл

# Брендові плитки банків/сервісів: ключ → назва, фон, колір тексту, короткий
# вордмарк. Малюємо CSS-плиткою (без імітації офіційних лого), тож виглядає
# охайно й одразу впізнавано за кольором та підписом.
BANK_PRESETS = {
    'mono':    {'name': 'monobank',   'bg': '#000000', 'fg': '#ffffff', 'label': 'mono'},
    'privat':  {'name': 'ПриватБанк', 'bg': '#3fae29', 'fg': '#ffffff', 'label': 'p24'},
    'pumb':    {'name': 'ПУМБ',       'bg': '#e2231a', 'fg': '#ffffff', 'label': 'ПУМБ'},
    'oschad':  {'name': 'Ощадбанк',   'bg': '#0a7d3e', 'fg': '#ffffff', 'label': 'Ощад'},
    'sense':   {'name': 'Sense Bank', 'bg': '#6d28d9', 'fg': '#ffffff', 'label': 'sense'},
    'abank':   {'name': 'A-Bank',     'bg': '#ff5a00', 'fg': '#ffffff', 'label': 'A'},
    'wise':    {'name': 'Wise',       'bg': '#9fe870', 'fg': '#163300', 'label': 'wise'},
    'paypal':  {'name': 'PayPal',     'bg': '#003087', 'fg': '#ffffff', 'label': 'PP'},
    'revolut': {'name': 'Revolut',    'bg': '#191c1f', 'fg': '#ffffff', 'label': 'R'},
    'cash':    {'name': 'Готівка',    'bg': '#15803d', 'fg': '#ffffff', 'label': '₴'},
}

# Підбірка емодзі, що добре читаються у маленькій картці.
EMOJI_PRESETS = [
    '💳', '💵', '💰', '🏦', '🪙', '💶', '💷', '💴',
    '🧾', '📈', '🛒', '🏧', '💎', '🔒', '⭐', '🔥',
]


def bank_presets_list():
    """Список банків для пікера (зберігає порядок словника)."""
    return [{'key': k, **v} for k, v in BANK_PRESETS.items()]


def bank_presets_map():
    """Карта ключ → {bg,fg,label} для клієнтського прев'ю в JS."""
    return {k: {'bg': v['bg'], 'fg': v['fg'], 'label': v['label']}
            for k, v in BANK_PRESETS.items()}


def process_account_icon(uploaded_file) -> str:
    """PNG/JPG/… → стиснутий WEBP data-URI прямокутної форми картки.

    Кадрує (cover) під співвідношення картки, тож яким би не був вихідний
    формат — результат завжди однакова акуратна прямокутна іконка. Повертає
    рядок виду ``data:image/webp;base64,...``. Кидає ``ValueError`` на
    некоректному чи завеликому файлі.
    """
    from PIL import Image, ImageOps

    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > ICON_MAX_UPLOAD:
        raise ValueError('Файл завеликий (макс. 8 МБ).')
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert('RGBA')
            fitted = ImageOps.fit(
                image, ICON_PX, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            output = io.BytesIO()
            fitted.save(output, format='WEBP', quality=82, method=6)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — будь-яка помилка декодування зображення
        raise ValueError('Не вдалося обробити зображення.') from exc
    encoded = base64.b64encode(output.getvalue()).decode('ascii')
    return f'data:image/webp;base64,{encoded}'


def icon_html(icon_type, icon_value, icon_data='', extra_class=''):
    """Безпечна розмітка прямокутної картки-іконки або '' якщо іконки немає."""
    cls = 'fin-acc-icon'
    if extra_class:
        cls += ' ' + extra_class
    if icon_type == 'emoji' and icon_value:
        return mark_safe(
            f'<span class="{escape(cls)} fin-acc-icon--emoji">{escape(icon_value)}</span>')
    if icon_type == 'bank':
        preset = BANK_PRESETS.get(icon_value)
        if preset:
            return format_html(
                '<span class="{} fin-acc-icon--bank" style="background:{};color:{}">{}</span>',
                cls, preset['bg'], preset['fg'], preset['label'])
    if icon_type == 'image' and icon_data:
        return format_html(
            '<span class="{} fin-acc-icon--image"><img src="{}" alt="" loading="lazy"></span>',
            cls, icon_data)
    return ''
