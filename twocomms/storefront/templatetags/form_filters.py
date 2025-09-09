from django import template

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
