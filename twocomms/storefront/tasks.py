import logging
import os
import sys
from datetime import timedelta
from pathlib import Path
import html

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

# Defensive import for image optimizer in case PYTHONPATH lacks project root
try:
    from twocomms.image_optimizer import ImageOptimizer
except ModuleNotFoundError:
    base_dir = Path(__file__).resolve().parent.parent  # twocomms/
    if str(base_dir.parent) not in sys.path:
        sys.path.append(str(base_dir.parent))
    try:
        from twocomms.image_optimizer import ImageOptimizer
    except ModuleNotFoundError:
        # Последний шанс: грузим модуль напрямую по пути
        module_path = base_dir / "image_optimizer.py"
        from importlib.machinery import SourceFileLoader
        ImageOptimizer = SourceFileLoader("twocomms.image_optimizer", str(module_path)).load_module().ImageOptimizer

from .models import Product, Category
from .seo_utils import SEOKeywordGenerator, SEOContentOptimizer
from .models import SurveySession
from .services.survey_engine import load_survey_definition
from .services.survey_reports import build_survey_report, get_survey_title, resolve_report_path
from orders.telegram_notifications import telegram_notifier

logger = logging.getLogger(__name__)

@shared_task
def generate_google_merchant_feed_task():
    """
    Celery task to generate Google Merchant feed.
    """
    try:
        logger.info("Starting Google Merchant feed generation task...")
        
        # Define output path
        media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
        output_path = os.path.join(media_root, 'google-merchant-v3.xml')
        
        # Call management command
        call_command('generate_google_merchant_feed', output=output_path, verbosity=0)
        
        logger.info(f"Google Merchant feed successfully generated at: {output_path}")
        
    except Exception as e:
        logger.error(f"Error generating Google Merchant feed: {e}", exc_info=True)


def _resolve_image_path(instance, field_name: str) -> Path | None:
    """
    Safely extracts absolute image path from a model instance field.
    """
    image_field = getattr(instance, field_name, None)
    if not image_field:
        return None
    try:
        path = Path(image_field.path)
    except Exception:
        return None
    return path if path.exists() else None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def optimize_image_field_task(self, model_label: str, object_id: int, field_name: str) -> bool:
    """
    Celery task to generate optimized (WebP/AVIF + responsive) versions for a single FileField/ImageField.

    Args:
        model_label: Full Django model label (e.g. 'storefront.Product')
        object_id: Primary key of the instance
        field_name: Image/File field name to optimize
    """
    try:
        Model = apps.get_model(model_label)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Cannot resolve model %s: %s", model_label, exc)
        return False

    instance = (
        Model.objects.filter(pk=object_id)
        .only(field_name)
        .first()
    )
    if not instance:
        logger.debug("Instance %s:%s not found for image optimization", model_label, object_id)
        return False

    image_path = _resolve_image_path(instance, field_name)
    if not image_path:
        logger.debug("No image path for %s.%s (id=%s)", model_label, field_name, object_id)
        return False

    optimized_dir = image_path.parent / "optimized"
    optimizer = ImageOptimizer()
    optimized_variants = optimizer.optimize_product_image(str(image_path))
    if not optimized_variants:
        logger.info("Nothing to optimize for %s", image_path.name)
        return False

    optimizer.save_optimized_images(optimized_variants, optimized_dir)
    logger.info(
        "Generated optimized variants for %s (%s)", image_path.name, optimized_dir.relative_to(settings.MEDIA_ROOT)
    )
    return True

@shared_task
def generate_ai_content_for_product_task(product_id):
    """
    Celery task to generate AI content for a product.
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # Check AI settings again (double check inside task)
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning(f"Skipping AI generation for product {product_id}: No API Key")
            return

        use_keywords = getattr(settings, 'USE_AI_KEYWORDS', False)
        use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
        
        if not use_keywords and not use_descriptions:
            return

        # Generate Keywords
        if use_keywords:
            ai_keywords = SEOKeywordGenerator.generate_product_keywords_ai(product)
            if ai_keywords:
                product.ai_keywords = ', '.join(ai_keywords)
        
        # Generate Description
        if use_descriptions:
            ai_description = SEOContentOptimizer.generate_ai_product_description(product)
            if ai_description:
                product.ai_description = ai_description
        
        # Save if changed
        if (use_keywords and product.ai_keywords) or (use_descriptions and product.ai_description):
            product.ai_content_generated = True
            product.save(update_fields=['ai_keywords', 'ai_description', 'ai_content_generated'])
            logger.info(f"AI content generated for product {product_id}")
            
    except Product.DoesNotExist:
        logger.warning(f"Product {product_id} not found for AI generation")
    except Exception as e:
        logger.error(f"Error generating AI content for product {product_id}: {e}", exc_info=True)

@shared_task
def generate_ai_content_for_category_task(category_id):
    """
    Celery task to generate AI content for a category.
    """
    try:
        category = Category.objects.get(id=category_id)
        
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return

        use_keywords = getattr(settings, 'USE_AI_KEYWORDS', False)
        use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
        
        if not use_keywords and not use_descriptions:
            return

        if use_keywords:
            ai_keywords = SEOKeywordGenerator.generate_category_keywords_ai(category)
            if ai_keywords:
                category.ai_keywords = ', '.join(ai_keywords)
        
        if use_descriptions:
            ai_description = SEOContentOptimizer.generate_ai_category_description(category)
            if ai_description:
                category.ai_description = ai_description
        
        if (use_keywords and category.ai_keywords) or (use_descriptions and category.ai_description):
            category.ai_content_generated = True
            category.save(update_fields=['ai_keywords', 'ai_description', 'ai_content_generated'])
            logger.info(f"AI content generated for category {category_id}")

    except Category.DoesNotExist:
        logger.warning(f"Category {category_id} not found for AI generation")
    except Exception as e:
        logger.error(f"Error generating AI content for category {category_id}: {e}", exc_info=True)


@shared_task
def send_survey_report_task(session_id: int, status: str) -> bool:
    """Generate and send survey report to Telegram asynchronously."""
    try:
        session = SurveySession.objects.select_related('user', 'awarded_promocode').get(id=session_id)
    except SurveySession.DoesNotExist:
        logger.warning("Survey session %s not found for report", session_id)
        return False

    definition = load_survey_definition()
    if not definition:
        logger.warning("Survey definition missing, report not sent for %s", session_id)
        return False

    report_path = resolve_report_path(session, definition)
    build_survey_report(session, definition, status, report_path)

    def fmt_dt(value):
        if not value:
            return "—"
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")

    title = html.escape(get_survey_title(definition))
    username = html.escape(session.user.username or f"user{session.user_id}")
    email = html.escape(session.user.email or "")
    status_labels = {
        "FINAL": "✅ Завершено",
        "PARTIAL": "⏳ Без активності",
        "UPDATED": "♻️ Оновлено",
    }
    status_text = status_labels.get(status, status)
    inactivity_minutes = int(
        (definition.get("policy", {}) or {}).get("inactivity", {}).get("partial_send_after_minutes", 10)
    )
    if status == "PARTIAL":
        status_text = f"{status_text} {inactivity_minutes} хв"

    caption_lines = [
        f"<b>{title}</b>",
        f"Статус: {status_text}",
        f"Користувач: {username} (ID {session.user_id})",
    ]
    if email:
        caption_lines.append(f"Email: {email}")

    promo_code = session.awarded_promocode.code if session.awarded_promocode else ""
    promo_expires = (
        fmt_dt(session.awarded_promocode.valid_until)
        if session.awarded_promocode and session.awarded_promocode.valid_until
        else ""
    )
    if status == "FINAL" and promo_code:
        caption_lines.append(f"Промокод: {promo_code} (до {promo_expires})")
    elif promo_code:
        caption_lines.append(f"Промокод: {promo_code}")

    caption_lines.extend([
        f"Початок: {fmt_dt(session.started_at)}",
        f"Остання активність: {fmt_dt(session.last_activity_at)}",
    ])
    if session.completed_at:
        caption_lines.append(f"Завершено: {fmt_dt(session.completed_at)}")

    caption = "\n".join(caption_lines)
    sent = telegram_notifier.send_admin_document(str(report_path), caption, filename=Path(report_path).name)
    if sent:
        session.report_status = status
        session.report_file_path = str(report_path)
        session.last_report_version = session.version
        session.last_report_sent_at = timezone.now()
        session.save(update_fields=[
            'report_status',
            'report_file_path',
            'last_report_version',
            'last_report_sent_at',
        ])
    return sent


def queue_survey_report(session_id: int, status: str) -> bool:
    """
    Try to enqueue survey report via Celery, fallback to sync when broker/worker is unavailable.
    """
    try:
        send_survey_report_task.delay(session_id, status)
        return True
    except Exception as exc:
        logger.warning(
            "Survey report queue failed (session=%s, status=%s): %s",
            session_id,
            status,
            exc,
            exc_info=True,
        )
        try:
            return bool(send_survey_report_task(session_id, status))
        except Exception as sync_exc:  # pragma: no cover - defensive
            logger.warning(
                "Survey report sync fallback failed (session=%s, status=%s): %s",
                session_id,
                status,
                sync_exc,
                exc_info=True,
            )
            return False


@shared_task
def check_survey_inactivity_task() -> int:
    """Check inactive survey sessions and send partial/updated reports."""
    definition = load_survey_definition()
    inactivity_policy = definition.get('policy', {}).get('inactivity', {}) if definition else {}
    threshold_minutes = int(inactivity_policy.get('partial_send_after_minutes', 10))
    allow_updates = bool(inactivity_policy.get('send_updates_after_partial', True))
    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)

    sessions = SurveySession.objects.filter(
        status='in_progress',
        last_activity_at__lte=cutoff,
    )
    triggered = 0
    for session in sessions:
        if session.report_status in ('PARTIAL', 'UPDATED') and not allow_updates:
            continue
        if session.last_report_version >= session.version and session.report_status in ('PARTIAL', 'UPDATED'):
            continue
        status = 'PARTIAL' if not session.report_status else 'UPDATED'
        queue_survey_report(session.id, status)
        triggered += 1
    return triggered
