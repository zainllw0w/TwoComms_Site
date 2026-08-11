from django.urls import path

from . import views, views_size_grids

urlpatterns = [
    # Єдиний редактор: додавання і редагування — ОДИН шаблон
    path("admin-panel/catalog/products/new/", views.editor, name="product_catalog_product_new"),
    path("admin-panel/catalog/products/<int:product_id>/edit/", views.editor, name="product_catalog_product_edit"),

    # JSON API (AJAX, без перезавантаження сторінки)
    path("admin-panel/catalog/api/product/save/", views.api_product_save, name="product_catalog_api_product_save"),
    path("admin-panel/catalog/api/product/delete/", views.api_product_delete, name="product_catalog_api_product_delete"),
    path("admin-panel/catalog/api/collections/save/", views.api_collection_save, name="product_catalog_api_collection_save"),
    path("admin-panel/catalog/api/collections/archive/", views.api_collection_archive, name="product_catalog_api_collection_archive"),
    path("admin-panel/catalog/api/collections/reorder/", views.api_collection_reorder, name="product_catalog_api_collection_reorder"),
    path("admin-panel/catalog/api/images/upload/", views.api_images_upload, name="product_catalog_api_images_upload"),
    path("admin-panel/catalog/api/images/update/", views.api_image_update, name="product_catalog_api_image_update"),
    path("admin-panel/catalog/api/images/optimization/status/", views.api_image_optimization_status, name="product_catalog_api_image_optimization_status"),
    path("admin-panel/catalog/api/images/optimization/retry/", views.api_image_optimization_retry, name="product_catalog_api_image_optimization_retry"),
    path("admin-panel/catalog/api/images/reorder/", views.api_images_reorder, name="product_catalog_api_images_reorder"),
    path("admin-panel/catalog/api/images/set-cover/", views.api_set_cover, name="product_catalog_api_set_cover"),
    path("admin-panel/catalog/api/variant/save/", views.api_variant_save, name="product_catalog_api_variant_save"),
    path("admin-panel/catalog/api/variant/delete/", views.api_variant_delete, name="product_catalog_api_variant_delete"),
    path("admin-panel/catalog/api/variant/reorder/", views.api_variants_reorder, name="product_catalog_api_variants_reorder"),
    path("admin-panel/catalog/api/colors/", views.api_colors, name="product_catalog_api_colors"),
    path("admin-panel/catalog/api/slug/", views.api_slug_preview, name="product_catalog_api_slug"),
    path("admin-panel/catalog/api/stock/", views.api_stock, name="product_catalog_api_stock"),
    path("admin-panel/catalog/api/feeds/", views.api_feeds, name="product_catalog_api_feeds"),
    path("admin-panel/catalog/api/feeds/create/", views.api_feed_create, name="product_catalog_api_feed_create"),
    path("admin-panel/catalog/api/feeds/rule/", views.api_feed_rule_save, name="product_catalog_api_feed_rule_save"),
    path("admin-panel/catalog/api/feeds/image/upload/", views.api_feed_only_image_upload, name="product_catalog_api_feed_image_upload"),
    path("admin-panel/catalog/api/feeds/image/delete/", views.api_feed_only_image_delete, name="product_catalog_api_feed_image_delete"),
    path("admin-panel/catalog/api/size-grids/", views_size_grids.api_size_grids, name="product_catalog_api_size_grids"),
    path("admin-panel/catalog/api/size-grids/save/", views_size_grids.api_size_grid_save, name="product_catalog_api_size_grid_save"),
    path("admin-panel/catalog/api/size-grids/duplicate/", views_size_grids.api_size_grid_duplicate, name="product_catalog_api_size_grid_duplicate"),
    path("admin-panel/catalog/api/size-grids/archive/", views_size_grids.api_size_grid_archive, name="product_catalog_api_size_grid_archive"),
    path("admin-panel/catalog/api/size-grids/preview/", views_size_grids.api_size_grid_preview, name="product_catalog_api_size_grid_preview"),
]
