"""
Product Builder Service - Helper functions for Admin Product Builder ViewSet.

This module provides serialization and payload generation functions
for the product builder admin interface.

TEMP: Stub implementations to prevent ModuleNotFoundError.
TODO: Implement full functionality when product builder UI is ready.
"""


def get_product_builder_payload(product=None, catalog=None):
    """
    Generate payload for product builder UI.
    
    Args:
        product: Product instance (for editing existing product)
        catalog: Catalog instance (for creating new product with pre-selected catalog)
        
    Returns:
        dict: Payload with product/catalog data, options, and size grids
    """
    # STUB implementation
    payload = {
        'product': None,
        'catalog': None,
        'catalogs': [],
        'options': [],
        'size_grids': [],
    }
    
    if product:
        payload['product'] = {
            'id': product.id,
            'title': product.title,
            'slug': product.slug,
            'catalog_id': product.catalog_id if hasattr(product, 'catalog_id') else None,
        }
        if hasattr(product, 'catalog') and product.catalog:
            payload['catalog'] = serialize_catalog(product.catalog)
    
    if catalog:
        payload['catalog'] = serialize_catalog(catalog)
    
    return payload


def serialize_catalog(catalog):
    """
    Serialize a Catalog instance with its options and size grids.
    
    Args:
        catalog: Catalog instance
        
    Returns:
        dict: Serialized catalog data
    """
    # STUB implementation
    return {
        'id': catalog.id,
        'name': catalog.name if hasattr(catalog, 'name') else '',
        'slug': catalog.slug if hasattr(catalog, 'slug') else '',
        'active': catalog.active if hasattr(catalog, 'active') else True,
        'options': [],
        'size_grids': [],
    }


def list_catalog_payloads(active_only=True):
    """
    List all catalogs with their options and size grids.
    
    Args:
        active_only: If True, only return active catalogs
        
    Returns:
        list: List of serialized catalog dictionaries
    """
    from ..models import Catalog
    
    # STUB implementation - return empty list or basic data
    queryset = Catalog.objects.all()
    if active_only and hasattr(Catalog, 'active'):
        queryset = queryset.filter(active=True)
    
    return [serialize_catalog(catalog) for catalog in queryset]

