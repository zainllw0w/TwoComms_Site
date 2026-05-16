from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


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


@staff_required
def debug_media(request): return JsonResponse({'status': 'ok'})
@staff_required
def debug_media_page(request): return render(request, 'admin/stub.html')
@staff_required
def debug_product_images(request): return JsonResponse({'status': 'ok'})
@staff_required
def dev_grant_admin(request): return redirect('home')

# ==================== STATIC PAGES STUBS ====================

# SEO molecular-upgrade US-4 (2026-05-16) — wholesale FAQ expanded from
# 3 to 8 questions covering pricing tiers, dropshipping, custom merch,
# production timelines, accounting docs, volunteer pricing and customer
# refusals. Mirrors keyword universe from audit/06 (опт, дропшипінг,
# мерч для команд, корпоративний друк) and feeds the FAQPage schema on
# /wholesale/.
WHOLESALE_FAQ_ITEMS = [
    {
        'question': _('Який мінімальний обсяг оптового замовлення у TwoComms?'),
        'answer': _('Класичний опт стартує від 8 одиниць однієї моделі або 30 одиниць у сумі по каталогу. Дропшипінг — без мінімального тиражу, працюємо одиничними позиціями за заявкою.'),
    },
    {
        'question': _('Які знижки діють на оптові партії?'),
        'answer': _('8-29 одиниць — 15 % від роздрібної ціни; 30-99 одиниць — 25 %; 100+ одиниць — 35 % і додатковий пакет послуг (упаковка з листівкою, спільна сесія фото, окремий менеджер). Для постійних оптовиків — індивідуальні умови за контрактом.'),
    },
    {
        'question': _('Як працює дропшипінг у TwoComms?'),
        'answer': _('Ви передаєте нам контакти кінцевого клієнта і вашу ціну продажу — ми відправляємо посилку від імені TwoComms (або у білій упаковці без логотипу за домовленістю). Вам — різниця між дроп-ціною і ціною продажу. Виплати — щотижня на картку або mono.'),
    },
    {
        'question': _('Чи можна замовити мерч під свій логотип?'),
        'answer': _('Так, через сторінку «Кастомний принт». Завантажуєте файл з логотипом, обираєте базу (футболка, худі, лонгслів), узгоджуєте розмір і розташування. Тираж — від 1 одиниці; партії від 50 — індивідуальна знижка.'),
    },
    {
        'question': _('Які терміни виготовлення великого тиражу?'),
        'answer': _('Тиражі до 50 одиниць — 5-7 робочих днів від погодження макета. 50-200 — 10-15 робочих днів. Більше 200 — 15-25 робочих днів. Терміни залежать від складності друку і поточної завантаженості виробництва у Харкові.'),
    },
    {
        'question': _('Чи виставляєте бухгалтерські документи з ПДВ?'),
        'answer': _('Так. Для юридичних осіб — повноцінний договір, рахунок-фактура, акт виконаних робіт, ПН з ПДВ. Працюємо за безготівковим розрахунком; передоплата 50 % при підписанні договору, остаток — після прийому партії.'),
    },
    {
        'question': _('Чи можна замовити одяг для волонтерського проєкту?'),
        'answer': _('Так. Для волонтерських ініціатив, благодійних фондів і ветеранських проєктів — пільгові тарифи (від 25 % знижки). Напишіть менеджеру з описом проєкту і метою — обговоримо умови і допоможемо із дизайном.'),
    },
    {
        'question': _('Що робити, якщо дроп-клієнт не викупив посилку?'),
        'answer': _('У дропшипінгу ви платите тільки 200 грн страхового платежу, які покривають доставку туди-назад при невикупі. Сам товар не закладений як збиток для дропшипера — повертається на склад TwoComms і знову доступний для продажу.'),
    },
]

# SEO molecular-upgrade US-4 — cooperation FAQ expanded from 3 to 7
# questions, including specific routes for stores, bloggers, designers,
# media partners and volunteer projects. Anchors B2B keyword cluster.
COOPERATION_FAQ_ITEMS = [
    {
        'question': _('Які формати співпраці доступні у TwoComms?'),
        'answer': _('Дропшипінг (без мінімального тиражу), класичний опт (від 8 одиниць), бренд-партнерства, спільні колекції, колаборації з дизайнерами, блогерами, інфлюенсерами, спортивними командами та медіа.'),
    },
    {
        'question': _('Кому підійде сторінка співпраці?'),
        'answer': _('Магазинам streetwear-одягу, шоурумам, локальним брендам, дизайнерам, контент-кріейторам, спортивним командам, школам стрільби, ветеранським організаціям, media-ресурсам, які хочуть запустити спільний проєкт або продавати TwoComms.'),
    },
    {
        'question': _('Куди звертатися для старту співпраці?'),
        'answer': _('Найшвидший шлях — написати у Telegram або через форму контактів. Ми відповідаємо протягом 1 години у робочий час; для масштабних B2B-проєктів — узгоджуємо персонального менеджера.'),
    },
    {
        'question': _('Чи робите спільні колекції з блогерами та дизайнерами?'),
        'answer': _('Так. Формати: одна спільна капсула (3-5 моделей під ваш дизайн), серія сезонних дропів, brand-collaboration з відсотком від продажів. Передплата за дизайн — від 5 000 грн залежно від обсягу робіт.'),
    },
    {
        'question': _('Які умови для блогерів та інфлюенсерів?'),
        'answer': _('Безкоштовний sample-набір (1-3 одиниці на вибір) для відгуку у соцмережах при аудиторії від 10 000 підписників. Reels / TikTok-рев’ю з мітками — додатковий промокод на 25 % для аудиторії. Для крупних блогерів (50 000+) — фіксована ставка за пост або відсоток від продажів.'),
    },
    {
        'question': _('Як працюєте з волонтерськими і благодійними проєктами?'),
        'answer': _('Пільгові тарифи (від 25 % знижки) для зареєстрованих ГО, благодійних фондів і ветеранських ініціатив. Реальний приклад — колаборація з Українським ветеранським фондом і фото з Євгеном Клопотенком. Напишіть менеджеру з реквізитами проєкту.'),
    },
    {
        'question': _('Чи продаєте на маркетплейсах і через дилерів?'),
        'answer': _('Так. Маркетплейси: Rozetka, Prom, Olx — через прямих партнерів-дилерів TwoComms. Якщо ви маркетплейс-дилер і хочете додати TwoComms у свій каталог — узгоджуємо ексклюзив на регіон або формат через менеджера.'),
    },
]


def add_print(request): return render(request, 'pages/stub.html')
def delivery_view(request): return render(request, 'pages/delivery.html')  # Assuming template exists
# Use real template for cooperation
def cooperation(request):
    return render(
        request,
        'pages/cooperation.html',
        {
            'faq_items': COOPERATION_FAQ_ITEMS,
            'breadcrumb_items': [
                {'name': _('Головна'), 'url': reverse('home')},
                {'name': _('Співпраця з TwoComms'), 'url': reverse('cooperation')},
            ],
        },
    )

# ==================== WHOLESALE STUBS ====================


def pricelist_redirect(request): return redirect('wholesale_page', permanent=True)
def pricelist_page(request): return redirect('wholesale_page', permanent=True)
def test_pricelist(request): return JsonResponse({'status': 'ok'})
def wholesale_page(request):
    return render(
        request,
        'pages/wholesale.html',
        {
            'faq_items': WHOLESALE_FAQ_ITEMS,
            'breadcrumb_items': [
                {'name': _('Головна'), 'url': reverse('home')},
                {'name': _('Оптові закупівлі та дропшипінг'), 'url': reverse('wholesale_page')},
            ],
        },
    )
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
