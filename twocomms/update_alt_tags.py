#!/usr/bin/env python3
"""
Скрипт для автоматического обновления alt-тегов в шаблонах TwoComms
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple

class AltTagsUpdater:
    """Обновляет alt-теги в шаблонах для SEO оптимизации"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.templates_dir = self.base_dir / 'twocomms_django_theme' / 'templates'
        
        # Маппинг для замены alt-тегов
        self.alt_replacements = {
            # Логотипы
            r'alt=["\']TwoComms логотип["\']': 'alt="TwoComms логотип - стріт & мілітарі одяг"',
            r'alt=["\']Logo["\']': 'alt="TwoComms логотип - стріт & мілітарі одяг"',
            r'alt=["\']Logo["\']': 'alt="TwoComms логотип"',
            
            # Аватары
            r'alt=["\']Аватар користувача["\']': 'alt="Аватар користувача - TwoComms"',
            r'alt=["\']Аватар["\']': 'alt="Аватар користувача - TwoComms"',
            r'alt=["\']Плейсхолдер аватара["\']': 'alt="Аватар користувача - TwoComms"',
            
            # Социальные сети
            r'alt=["\']Google["\']': 'alt="Вхід через Google - TwoComms"',
            
            # Товары (общие)
            r'alt=["\']{{ product\.title }}\["\']': 'alt="{{ product.title }} - стріт одяг TwoComms"',
            r'alt=["\']{{ p\.title }}\["\']': 'alt="{{ p.title }} - стріт одяг TwoComms"',
            
            # Категории
            r'alt=["\']{{ c\.name }}\["\']': 'alt="{{ c.name }} іконка - TwoComms"',
            
            # Корзина и заказы
            r'alt=["\']{{ it\.product\.title }}\["\']': 'alt="{{ it.product.title }} - товар у кошику TwoComms"',
            r'alt=["\']{{ item\.product\.title }}\["\']': 'alt="{{ item.product.title }} - товар у замовленні TwoComms"',
        }
        
        # Шаблоны для автоматической генерации
        self.alt_templates = {
            'product_main': '{{ product.title }} - {{ product.category.name }} TwoComms',
            'product_gallery': '{{ product.title }} - фото {{ forloop.counter }} TwoComms',
            'category_icon': '{{ c.name }} іконка - TwoComms',
            'logo': 'TwoComms логотип - стріт & мілітарі одяг',
            'avatar': 'Аватар користувача - TwoComms',
            'social': 'Вхід через {{ social_network }} - TwoComms'
        }
    
    def update_all_templates(self) -> Dict:
        """Обновляет все шаблоны"""
        results = {
            'updated_files': [],
            'total_changes': 0,
            'errors': [],
            'summary': {}
        }
        
        if not self.templates_dir.exists():
            results['errors'].append(f"Папка шаблонів не знайдена: {self.templates_dir}")
            return results
        
        # Обрабатываем все HTML файлы
        for template_file in self.templates_dir.rglob('*.html'):
            try:
                file_result = self.update_template_file(template_file)
                if file_result['changes'] > 0:
                    results['updated_files'].append(file_result)
                    results['total_changes'] += file_result['changes']
            except Exception as e:
                results['errors'].append(f"Помилка обробки {template_file.name}: {str(e)}")
        
        # Генерируем сводку
        results['summary'] = self.generate_summary(results)
        
        return results
    
    def update_template_file(self, template_path: Path) -> Dict:
        """Обновляет конкретный шаблон"""
        result = {
            'file': str(template_path.relative_to(self.base_dir)),
            'changes': 0,
            'replacements': [],
            'backup_created': False
        }
        
        try:
            # Читаем файл
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Создаем бэкап
            backup_path = template_path.with_suffix('.html.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            result['backup_created'] = True
            
            # Применяем замены
            for pattern, replacement in self.alt_replacements.items():
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    result['replacements'].append({
                        'pattern': pattern,
                        'replacement': replacement,
                        'count': len(re.findall(pattern, content))
                    })
                    content = new_content
            
            # Дополнительная обработка для конкретных файлов
            content = self.apply_file_specific_updates(template_path, content)
            
            # Подсчитываем изменения
            result['changes'] = len(result['replacements'])
            
            # Сохраняем обновленный файл
            if content != original_content:
                with open(template_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def apply_file_specific_updates(self, template_path: Path, content: str) -> str:
        """Применяет специфичные для файла обновления"""
        file_name = template_path.name
        
        # Обновления для главной страницы
        if file_name == 'index.html':
            content = self.update_index_page(content)
        
        # Обновления для страницы товара
        elif file_name == 'product_detail.html':
            content = self.update_product_detail_page(content)
        
        # Обновления для базового шаблона
        elif file_name == 'base.html':
            content = self.update_base_template(content)
        
        # Обновления для карточек товаров
        elif file_name == 'product_card.html':
            content = self.update_product_card(content)
        
        # Обновления для корзины
        elif file_name == 'cart.html':
            content = self.update_cart_page(content)
        
        return content
    
    def update_index_page(self, content: str) -> str:
        """Обновляет главную страницу"""
        # Улучшаем alt-тексты для рекомендуемого товара
        content = re.sub(
            r'alt="([^"]*{{ featured\.title }}[^"]*)"',
            r'alt="{{ featured.title }} - рекомендуємий товар TwoComms"',
            content
        )
        
        # Улучшаем alt-тексты для категорий
        content = re.sub(
            r'alt="{{ c\.name }}"',
            r'alt="{{ c.name }} категорія - TwoComms"',
            content
        )
        
        return content
    
    def update_product_detail_page(self, content: str) -> str:
        """Обновляет страницу товара"""
        # Улучшаем alt-тексты для основного изображения
        content = re.sub(
            r'alt="{{ product\.title }}"',
            r'alt="{{ product.title }} - головне фото TwoComms"',
            content
        )
        
        # Улучшаем alt-тексты для миниатюр
        content = re.sub(
            r'alt="{{ product\.title\|escapejs }} — фото"',
            r'alt="{{ product.title }} - фото {{ forloop.counter }} TwoComms"',
            content
        )
        
        return content
    
    def update_base_template(self, content: str) -> str:
        """Обновляет базовый шаблон"""
        # Улучшаем alt-тексты для аватаров
        content = re.sub(
            r'alt="Аватар користувача"',
            r'alt="Аватар користувача - TwoComms"',
            content
        )
        
        # Улучшаем alt-тексты для социальных сетей
        content = re.sub(
            r'alt="Google"',
            r'alt="Вхід через Google - TwoComms"',
            content
        )
        
        return content
    
    def update_product_card(self, content: str) -> str:
        """Обновляет карточку товара"""
        # Улучшаем alt-тексты для товаров в каталоге
        content = re.sub(
            r'alt="{{ p\.title }}"',
            r'alt="{{ p.title }} - {{ p.category.name }} TwoComms"',
            content
        )
        
        return content
    
    def update_cart_page(self, content: str) -> str:
        """Обновляет страницу корзины"""
        # Улучшаем alt-тексты для товаров в корзине
        content = re.sub(
            r'alt="{{ it\.product\.title }}"',
            r'alt="{{ it.product.title }} - товар у кошику TwoComms"',
            content
        )
        
        return content
    
    def generate_summary(self, results: Dict) -> Dict:
        """Генерирует сводку изменений"""
        summary = {
            'files_updated': len(results['updated_files']),
            'total_changes': results['total_changes'],
            'errors_count': len(results['errors']),
            'most_changed_files': [],
            'common_replacements': {}
        }
        
        # Находим файлы с наибольшим количеством изменений
        sorted_files = sorted(results['updated_files'], key=lambda x: x['changes'], reverse=True)
        summary['most_changed_files'] = sorted_files[:5]
        
        # Подсчитываем общие замены
        replacement_counts = {}
        for file_result in results['updated_files']:
            for replacement in file_result['replacements']:
                pattern = replacement['pattern']
                count = replacement['count']
                replacement_counts[pattern] = replacement_counts.get(pattern, 0) + count
        
        summary['common_replacements'] = dict(sorted(replacement_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return summary
    
    def create_seo_report(self, results: Dict) -> str:
        """Создает SEO отчет"""
        report = f"""
# SEO Оптимізація Alt-тегів TwoComms

## Загальна статистика
- Оновлено файлів: {results['summary']['files_updated']}
- Загальна кількість змін: {results['summary']['total_changes']}
- Помилок: {results['summary']['errors_count']}

## Найбільш оновлені файли
"""
        
        for file_result in results['summary']['most_changed_files']:
            report += f"- {file_result['file']}: {file_result['changes']} змін\n"
        
        report += f"""
## Найчастіші заміни
"""
        
        for pattern, count in results['summary']['common_replacements'].items():
            report += f"- {pattern}: {count} разів\n"
        
        if results['errors']:
            report += f"""
## Помилки
"""
            for error in results['errors']:
                report += f"- {error}\n"
        
        report += f"""
## Рекомендації
1. Перевірте оновлені файли в браузері
2. Протестуйте SEO-оптимізацію
3. Моніторьте зміни в пошукових системах
4. Додайте нові alt-тексти для майбутніх зображень

## Наступні кроки
1. Створити систему автоматичної генерації alt-текстів
2. Додати валідацію alt-текстів
3. Налаштувати моніторинг SEO показників
"""
        
        return report


def main():
    """Основная функция"""
    print("🚀 Оновлення alt-тегів TwoComms для SEO...")
    
    updater = AltTagsUpdater()
    results = updater.update_all_templates()
    
    # Сохраняем результаты
    with open('alt_tags_update_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Создаем отчет
    report = updater.create_seo_report(results)
    with open('alt_tags_seo_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ Оновлення завершено!")
    print(f"📊 Статистика:")
    print(f"   - Оновлено файлів: {results['summary']['files_updated']}")
    print(f"   - Загальна кількість змін: {results['summary']['total_changes']}")
    print(f"   - Помилок: {results['summary']['errors_count']}")
    
    if results['errors']:
        print(f"\n⚠️  Помилки:")
        for error in results['errors'][:3]:
            print(f"   - {error}")
    
    print(f"\n📄 Звіт збережено в alt_tags_seo_report.md")
    print(f"📊 Детальні результати в alt_tags_update_results.json")
    
    return results


if __name__ == '__main__':
    main()
