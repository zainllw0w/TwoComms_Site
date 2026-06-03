"""Signals складу.

1. post_migrate — гарантує наявність Group 'warehouse_admins'.
2. Авто-конвертація завантажених зображень принтів у WebP при збереженні
   (PNG/JPEG → WebP зі збереженням прозорості), видалення попереднього
   файлу при заміні та видалення файлу при видаленні запису. Економить
   місце на сервері й уніфікує превʼю принтів.
"""
from __future__ import annotations

import logging

from django.apps import apps
from django.db.models.signals import post_delete, post_migrate, post_save, pre_save
from django.dispatch import receiver

from warehouse.permissions import WAREHOUSE_GROUP_NAME

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def ensure_warehouse_group(sender, **kwargs):
    """Гарантує наявність групи 'warehouse_admins' у БД."""
    if sender.label != "warehouse":
        return
    try:
        Group = apps.get_model("auth", "Group")
        Group.objects.get_or_create(name=WAREHOUSE_GROUP_NAME)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Авто-WebP для зображень принтів
# ---------------------------------------------------------------------------

# Розміри превʼю: квадратний кеп — принт впізнаваний, файл маленький.
# Прозорість зберігається (RGBA → WebP з alpha) у process_image_field.
_PRINT_IMAGE_LIMITS = {
    # model_label: {field_name: (max_w, max_h)}
    "warehouse.Print": {"main_image": (900, 900)},
    "warehouse.PrintColorVariant": {"image": (700, 700)},
}


def _intake_targets_for(sender):
    label = f"{sender._meta.app_label}.{sender.__name__}"
    return _PRINT_IMAGE_LIMITS.get(label)


@receiver(pre_save)
def warehouse_convert_print_images(sender, instance, raw=False, **kwargs):
    """Конвертує свіже завантаження у WebP та запамʼятовує старий файл.

    Працює лише для моделей із ``_PRINT_IMAGE_LIMITS``. Старий файл
    зберігаємо в ``instance._wh_old_files`` щоб видалити його у post_save,
    якщо зображення дійсно замінили.
    """
    if raw:
        return
    targets = _intake_targets_for(sender)
    if not targets:
        return

    try:
        from storefront.services.image_intake import process_image_field
    except Exception:  # pragma: no cover - storefront завжди доступний
        process_image_field = None

    old_files: dict[str, str] = {}
    # Поточні (старі) імена файлів — лише якщо запис уже існує в БД.
    if instance.pk:
        try:
            previous = sender.objects.only(*targets.keys()).get(pk=instance.pk)
        except sender.DoesNotExist:
            previous = None
        if previous is not None:
            for fname in targets:
                old_field = getattr(previous, fname, None)
                old_files[fname] = old_field.name if old_field else ""

    for fname, (max_w, max_h) in targets.items():
        field = getattr(instance, fname, None)
        if not field:
            continue
        if process_image_field is None:
            continue
        try:
            # min_bytes=0 → конвертуємо навіть маленькі принти у WebP.
            process_image_field(field, max_width=max_w, max_height=max_h, min_bytes=0)
        except Exception as exc:  # pragma: no cover - захисна гілка
            logger.warning(
                "warehouse image intake failed on %s.%s (id=%s): %s",
                sender.__name__, fname, getattr(instance, "pk", None), exc,
            )

    instance._wh_old_files = old_files


@receiver(post_save)
def warehouse_cleanup_replaced_print_images(sender, instance, **kwargs):
    """Видаляє попередній файл зображення, якщо його замінили новим."""
    targets = _intake_targets_for(sender)
    if not targets:
        return
    old_files = getattr(instance, "_wh_old_files", None)
    if not old_files:
        return
    for fname in targets:
        old_name = old_files.get(fname) or ""
        if not old_name:
            continue
        new_field = getattr(instance, fname, None)
        new_name = new_field.name if new_field else ""
        if old_name and old_name != new_name:
            try:
                storage = new_field.storage if new_field else None
                if storage and storage.exists(old_name):
                    storage.delete(old_name)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Failed to delete replaced image %s: %s", old_name, exc
                )
    instance._wh_old_files = {}


@receiver(post_delete)
def warehouse_delete_print_images(sender, instance, **kwargs):
    """Прибирає файли зображень при видаленні запису (Print / варіант)."""
    targets = _intake_targets_for(sender)
    if not targets:
        return
    for fname in targets:
        field = getattr(instance, fname, None)
        if not field:
            continue
        name = field.name
        if not name:
            continue
        try:
            if field.storage.exists(name):
                field.storage.delete(name)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to delete image %s on delete: %s", name, exc)
