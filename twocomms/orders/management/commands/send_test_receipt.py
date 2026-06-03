"""
Надсилає тестовий лист-квитанцію на вказаний email.

Використання:
  python manage.py send_test_receipt --email pilimcenu270795@gmail.com
  python manage.py send_test_receipt --email a@b.com --order TWC30102025N01
  python manage.py send_test_receipt --email a@b.com --demo
  python manage.py send_test_receipt --email a@b.com --demo --dump-html /path/out.html

Логіка вибору замовлення:
  1) якщо задано --order <number/id> — беремо саме його;
  2) інакше беремо останнє замовлення з оплатою/передплатою;
  3) якщо нічого нема або задано --demo — створюємо тимчасове демо-замовлення
     в БД (з реальними товарами для коректних фото) і видаляємо його після.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from orders.models import Order, OrderItem
from storefront.models import Product
from orders.email_receipt import build_order_receipt_email, send_order_receipt_email


class Command(BaseCommand):
    help = "Надсилає тестовий лист-квитанцію на вказаний email."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Куди надіслати лист')
        parser.add_argument('--order', default='', help='Номер або ID замовлення (опціонально)')
        parser.add_argument('--demo', action='store_true', help='Примусово створити демо-замовлення')
        parser.add_argument('--dump-html', default='', help='Зберегти HTML листа у файл (без відправки)')

    def handle(self, *args, **options):
        email = options['email'].strip()
        order_ref = (options.get('order') or '').strip()
        use_demo = options.get('demo')
        dump_html = (options.get('dump_html') or '').strip()

        order = None
        created_demo = False

        if not use_demo:
            if order_ref:
                order = (
                    Order.objects.filter(order_number=order_ref).first()
                    or (Order.objects.filter(pk=order_ref).first() if order_ref.isdigit() else None)
                )
                if not order:
                    self.stderr.write(self.style.WARNING(f'Замовлення {order_ref} не знайдено, створюю демо.'))
            if order is None:
                order = (
                    Order.objects.filter(payment_status__in=['paid', 'prepaid'])
                    .order_by('-created')
                    .first()
                )

        if order is None:
            order = self._create_demo_order()
            created_demo = True
            self.stdout.write(f'Створено тимчасове демо-замовлення {order.order_number} (id={order.pk}).')
        else:
            self.stdout.write(f'Використовую замовлення {order.order_number} (id={order.pk}).')

        try:
            if dump_html:
                built = build_order_receipt_email(order)
                with open(dump_html, 'w', encoding='utf-8') as fh:
                    fh.write(built['html'])
                self.stdout.write(self.style.SUCCESS(f'HTML збережено у {dump_html}'))
                return

            ok, err = send_order_receipt_email(order, force=True, recipient=email)
            if ok:
                self.stdout.write(self.style.SUCCESS(f'Лист надіслано на {email}.'))
            else:
                self.stderr.write(self.style.ERROR(f'Помилка відправки: {err}'))
        finally:
            if created_demo:
                demo_pk = order.pk
                try:
                    order.delete()
                    self.stdout.write(f'Демо-замовлення {demo_pk} видалено.')
                except Exception as exc:
                    self.stderr.write(self.style.WARNING(f'Не вдалося видалити демо-замовлення {demo_pk}: {exc}'))

    @transaction.atomic
    def _create_demo_order(self):
        """Створює тимчасове замовлення з 1-2 реальними товарами (для фото)."""
        order = Order.objects.create(
            full_name='Іван Петренко',
            phone='+380501234567',
            email='',
            city='Київ',
            np_office='Відділення №1, вул. Хрещатик, 1',
            pay_type='online_full',
            payment_status='paid',
            total_sum=Decimal('0'),
            discount_amount=Decimal('200'),
            status='new',
        )

        products = list(Product.objects.all()[:2])
        total = Decimal('0')
        if products:
            for p in products:
                try:
                    unit = Decimal(str(p.final_price or p.price or 500))
                except Exception:
                    unit = Decimal('500')
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    title=p.title,
                    size='M',
                    fit_option_label='Regular',
                    qty=1,
                    unit_price=unit,
                    line_total=unit,
                )
                total += unit
        else:
            for title, price in (('Худі Tactical Black', Decimal('1350')), ('Футболка Street Wolf', Decimal('449'))):
                OrderItem.objects.create(
                    order=order,
                    product=None,
                    title=title,
                    size='M',
                    qty=1,
                    unit_price=price,
                    line_total=price,
                    is_custom=True,
                )
                total += price

        order.total_sum = (total - order.discount_amount) if total > order.discount_amount else total
        order.save(update_fields=['total_sum'])
        return order
