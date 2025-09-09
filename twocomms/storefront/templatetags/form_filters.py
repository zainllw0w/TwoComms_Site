from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
import os
from urllib.parse import urlparse

register = template.Library()


@register.filter(name='add_class')
def add_class(bound_field, css_class):
    """Добавляет CSS-класс к виджету поля формы при рендере.
    Использование в шаблоне: {{ form.field|add_class:"form-control" }}
    """
    try:
        widget = bound_field.field.widget
        attrs = widget.attrs.copy()
        if 'class' in attrs and attrs['class']:
            attrs['class'] = f"{attrs['class']} {css_class}"
        else:
            attrs['class'] = css_class
        return bound_field.as_widget(attrs=attrs)
    except Exception:
        # На всякий случай, не падаем в шаблоне
        return bound_field


# ===== Изображения: picture с WebP, lazy/eager и fetchpriority =====
def _to_webp_path(url: str) -> str:
    try:
        parsed = urlparse(url)
        path = parsed.path
        base, _ = os.path.splitext(path)
        return base + '.webp'
    except Exception:
        return url


@register.simple_tag
def picture(img_url: str, alt: str = "", width: int = None, height: int = None, cls: str = "", fetch: str = "auto", eager: bool = False):
    webp_url = _to_webp_path(img_url)
    webp_exists = False
    try:
        cand = os.path.join(settings.MEDIA_ROOT, webp_url.replace(settings.MEDIA_URL, '').lstrip('/'))
        if os.path.exists(cand):
            webp_exists = True
        else:
            cand = os.path.join(settings.STATIC_ROOT, webp_url.replace(settings.STATIC_URL, '').lstrip('/'))
            webp_exists = os.path.exists(cand)
    except Exception:
        webp_exists = False

    wh = ''
    if width: wh += f' width="{int(width)}"'
    if height: wh += f' height="{int(height)}"'
    loading = 'eager' if eager else 'lazy'
    priority = 'high' if eager else 'low'
    cls_attr = f' class="{cls}"' if cls else ''

    if webp_exists:
        html = f"<picture><source srcset=\"{webp_url}\" type=\"image/webp\"><img src=\"{img_url}\" alt=\"{alt}\" loading=\"{loading}\" fetchpriority=\"{priority}\" decoding=\"async\"{wh}{cls_attr}></picture>"
    else:
        html = f"<img src=\"{img_url}\" alt=\"{alt}\" loading=\"{loading}\" fetchpriority=\"{priority}\" decoding=\"async\"{wh}{cls_attr}>"
    return mark_safe(html)
