from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required, user_passes_test

def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff)(view_func)

# ==================== OFFLINE STORES STUBS ====================
@staff_required
def admin_offline_stores(request): return render(request, 'admin/stub.html')
@staff_required
def admin_offline_store_create(request): return redirect('admin_offline_stores')
@staff_required
def admin_offline_store_edit(request, pk): return redirect('admin_offline_stores')
@staff_required
def admin_offline_store_toggle(request, pk): return redirect('admin_offline_stores')
@staff_required
def admin_offline_store_delete(request, pk): return redirect('admin_offline_stores')

# Store Management
@staff_required
def admin_store_management(request, store_id): return render(request, 'admin/stub.html')
@staff_required
def admin_store_add_product_to_order(request, store_id): return JsonResponse({'status': 'error'})
@staff_required
def admin_store_get_order_items(request, store_id, order_id): return JsonResponse({'items': []})
@staff_required
def admin_store_get_product_colors(request, store_id, product_id): return JsonResponse({'colors': []})
@staff_required
def admin_store_remove_product_from_order(request, store_id, order_id, item_id): return JsonResponse({'status': 'ok'})
@staff_required
def admin_store_add_products_to_store(request, store_id): return redirect('admin_store_management', store_id=store_id)
@staff_required
def admin_store_generate_invoice(request, store_id): return redirect('admin_store_management', store_id=store_id)
@staff_required
def admin_store_update_product(request, store_id, product_id): return JsonResponse({'status': 'ok'})
@staff_required
def admin_store_mark_product_sold(request, store_id, product_id): return JsonResponse({'status': 'ok'})
@staff_required
def admin_store_remove_product(request, store_id, product_id): return JsonResponse({'status': 'ok'})

# ==================== PRINT PROPOSALS STUBS ====================
@staff_required
def admin_print_proposal_update_status(request): return JsonResponse({'status': 'ok'})
@staff_required
def admin_print_proposal_award_points(request): return JsonResponse({'status': 'ok'})
@staff_required
def admin_print_proposal_award_promocode(request): return JsonResponse({'status': 'ok'})

# ==================== API & DEBUG STUBS ====================
def api_colors(request): return JsonResponse({'colors': []})
@staff_required
def debug_media(request): return JsonResponse({'status': 'ok'})
@staff_required
def debug_media_page(request): return render(request, 'admin/stub.html')
@staff_required
def debug_product_images(request): return JsonResponse({'status': 'ok'})
@staff_required
def dev_grant_admin(request): return redirect('home')

# ==================== STATIC PAGES STUBS ====================
def add_print(request): return render(request, 'pages/stub.html')
def delivery_view(request): return render(request, 'pages/delivery.html') # Assuming template exists
# Use real template for cooperation
def cooperation(request): return render(request, 'pages/cooperation.html')

# ==================== WHOLESALE STUBS ====================
def pricelist_redirect(request): return redirect('home')
def pricelist_page(request): return render(request, 'pages/wholesale.html')
def test_pricelist(request): return JsonResponse({'status': 'ok'})
def wholesale_page(request): return render(request, 'pages/wholesale.html')
def wholesale_order_form(request): return render(request, 'pages/wholesale_order_form.html')
def generate_wholesale_invoice(request): return redirect('wholesale_page')
def download_invoice_file(request, invoice_id): raise Http404
def delete_wholesale_invoice(request, invoice_id): return redirect('wholesale_page')
def check_invoice_approval_status(request, invoice_id): return JsonResponse({'status': 'ok'})
def check_payment_status(request, invoice_id): return JsonResponse({'status': 'ok'})
def debug_invoices(request): return JsonResponse({'status': 'ok'})
def create_wholesale_payment(request): return JsonResponse({'status': 'error'})
def wholesale_payment_webhook(request): return JsonResponse({'status': 'ok'})
def get_user_invoices(request): return JsonResponse({'invoices': []})

# ==================== INVOICE ADMIN STUBS ====================
@staff_required
def admin_update_invoice_status(request, invoice_id): return JsonResponse({'status': 'ok'})
@staff_required
def toggle_invoice_approval(request, invoice_id): return JsonResponse({'status': 'ok'})
@staff_required
def toggle_invoice_payment_status(request, invoice_id): return JsonResponse({'status': 'ok'})
@staff_required
def reset_all_invoices_status(request): return redirect('admin_panel')

# ==================== DROPSHIP ADMIN STUBS ====================
@staff_required
def admin_update_dropship_status(request, order_id): return JsonResponse({'status': 'ok'})
@staff_required
def admin_get_dropship_order(request, order_id): return JsonResponse({'order': {}})
@staff_required
def admin_update_dropship_order(request, order_id): return JsonResponse({'status': 'ok'})
@staff_required
def admin_delete_dropship_order(request, order_id): return JsonResponse({'status': 'ok'})

# ==================== MONOBANK QUICK STUBS ====================
def monobank_create_checkout(request): return redirect('cart')
def monobank_return(request): return redirect('home')
