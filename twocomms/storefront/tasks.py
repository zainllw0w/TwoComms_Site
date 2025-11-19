import logging
import os
from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from .models import Product, Category
from .seo_utils import SEOKeywordGenerator, SEOContentOptimizer

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
