from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserPoints

class Command(BaseCommand):
    help = 'Создает объекты UserPoints для всех пользователей, у которых их нет'

    def handle(self, *args, **options):
        self.stdout.write('Создание отсутствующих объектов UserPoints...')
        
        # Находим всех пользователей без UserPoints
        users_without_points = User.objects.filter(points__isnull=True)
        
        created_count = 0
        for user in users_without_points:
            UserPoints.objects.create(user=user)
            created_count += 1
            self.stdout.write(f'  ✅ Создан UserPoints для пользователя: {user.username}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано {created_count} объектов UserPoints для пользователей без баллов'
            )
        )
