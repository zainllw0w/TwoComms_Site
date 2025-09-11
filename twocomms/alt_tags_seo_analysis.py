#!/usr/bin/env python3
"""
Комплексный анализ и SEO оптимизация alt-тегов для TwoComms
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.text import slugify

class AltTagsSEOAnalyzer:
    """Анализатор alt-тегов для SEO оптимизации"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.templates_dir = self.base_dir / 'twocomms_django_theme' / 'templates'
        self.media_dir = self.base_dir / 'media'
        
        # SEO ключевые слова для alt-текстов
        self.seo_keywords = {
            'product_types': [
                'футболка', 'худі', 'лонгслів', 'світшот', 'толстовка',
                'базова футболка', 'принтована футболка', 'чоловіча футболка',
                'жіноча футболка', 'унісекс футболка', 'стильна футболка'
            ],
            'colors': [
                'чорна', 'біла', 'сіра', 'зелена', 'синя', 'червона',
                'коричнева', 'бежева', 'рожева', 'жовта', 'фіолетова'
            ],
            'styles': [
                'стріт стиль', 'мілітарі стиль', 'ексклюзивний дизайн',
                'модний одяг', 'трендовий одяг', 'якісний одяг',
                'одяг з характером', 'український бренд'
            ],
            'brand': [
                'TwoComms', 'TwoComms логотип', 'TwoComms бренд',
                'офіційний TwoComms', 'TwoComms магазин'
            ]
        }
        
        # Проблемные alt-тексты для исправления
        self.problematic_alts = [
            '', 'Logo', 'Logo', 'Аватар', 'Плейсхолдер аватара',
            'Поточне зображення', 'Скріншот оплати', 'фото'
        ]
    
    def analyze_current_alt_tags(self) -> Dict:
        """Анализирует текущие alt-теги на сайте"""
        analysis = {
            'total_images': 0,
            'images_with_alt': 0,
            'images_without_alt': 0,
            'problematic_alts': 0,
            'good_alts': 0,
            'templates_analyzed': [],
            'issues': [],
            'recommendations': []
        }
        
        # Анализируем все шаблоны
        for template_file in self.templates_dir.rglob('*.html'):
            template_analysis = self._analyze_template_alt_tags(template_file)
            if template_analysis['total_images'] > 0:
                analysis['templates_analyzed'].append(template_analysis)
                analysis['total_images'] += template_analysis['total_images']
                analysis['images_with_alt'] += template_analysis['images_with_alt']
                analysis['images_without_alt'] += template_analysis['images_without_alt']
                analysis['problematic_alts'] += template_analysis['problematic_alts']
                analysis['good_alts'] += template_analysis['good_alts']
                analysis['issues'].extend(template_analysis['issues'])
        
        # Генерируем рекомендации
        analysis['recommendations'] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_template_alt_tags(self, template_path: Path) -> Dict:
        """Анализирует alt-теги в конкретном шаблоне"""
        analysis = {
            'template': str(template_path.relative_to(self.base_dir)),
            'total_images': 0,
            'images_with_alt': 0,
            'images_without_alt': 0,
            'problematic_alts': 0,
            'good_alts': 0,
            'issues': [],
            'images': []
        }
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Находим все img теги
            img_pattern = r'<img[^>]*>'
            img_tags = re.findall(img_pattern, content, re.IGNORECASE)
            
            for img_tag in img_tags:
                analysis['total_images'] += 1
                
                # Извлекаем alt атрибут
                alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
                alt_text = alt_match.group(1) if alt_match else ''
                
                # Анализируем alt-текст
                alt_analysis = self._analyze_alt_text(alt_text, img_tag)
                
                analysis['images'].append({
                    'tag': img_tag,
                    'alt_text': alt_text,
                    'analysis': alt_analysis
                })
                
                if alt_text:
                    analysis['images_with_alt'] += 1
                    if alt_analysis['is_good']:
                        analysis['good_alts'] += 1
                    else:
                        analysis['problematic_alts'] += 1
                        analysis['issues'].append(f"Проблемний alt-текст: '{alt_text}' в {template_path.name}")
                else:
                    analysis['images_without_alt'] += 1
                    analysis['issues'].append(f"Відсутній alt-текст в {template_path.name}")
        
        except Exception as e:
            analysis['issues'].append(f"Помилка аналізу {template_path.name}: {str(e)}")
        
        return analysis
    
    def _analyze_alt_text(self, alt_text: str, img_tag: str) -> Dict:
        """Анализирует качество alt-текста"""
        analysis = {
            'text': alt_text,
            'length': len(alt_text),
            'is_good': False,
            'issues': [],
            'seo_score': 0,
            'suggestions': []
        }
        
        # Проверяем длину
        if len(alt_text) < 5:
            analysis['issues'].append("Занадто короткий alt-текст")
        elif len(alt_text) > 125:
            analysis['issues'].append("Занадто довгий alt-текст")
        else:
            analysis['seo_score'] += 2
        
        # Проверяем на проблемные тексты
        if alt_text.lower() in [alt.lower() for alt in self.problematic_alts]:
            analysis['issues'].append("Генеричний або проблемний alt-текст")
        else:
            analysis['seo_score'] += 3
        
        # Проверяем наличие SEO ключевых слов
        alt_lower = alt_text.lower()
        seo_keywords_found = 0
        
        for category, keywords in self.seo_keywords.items():
            for keyword in keywords:
                if keyword.lower() in alt_lower:
                    seo_keywords_found += 1
                    break
        
        if seo_keywords_found > 0:
            analysis['seo_score'] += seo_keywords_found
        else:
            analysis['issues'].append("Відсутні SEO ключові слова")
        
        # Проверяем на спам
        if alt_text.count('TwoComms') > 2:
            analysis['issues'].append("Переспам бренду")
            analysis['seo_score'] -= 1
        
        # Определяем общую оценку
        analysis['is_good'] = analysis['seo_score'] >= 4 and len(analysis['issues']) == 0
        
        return analysis
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Генерирует рекомендации по улучшению alt-тегов"""
        recommendations = []
        
        # Общие рекомендации
        if analysis['images_without_alt'] > 0:
            recommendations.append(f"Додати alt-тексти до {analysis['images_without_alt']} зображень")
        
        if analysis['problematic_alts'] > 0:
            recommendations.append(f"Покращити {analysis['problematic_alts']} проблемних alt-текстів")
        
        # Специфические рекомендации
        recommendations.extend([
            "Використовувати описові alt-тексти з ключовими словами",
            "Включати тип товару, колір та бренд у alt-текст",
            "Уникати генеричних текстів типу 'Logo' або 'Зображення'",
            "Обмежити довжину alt-тексту до 125 символів",
            "Використовувати українську мову для кращої локальної SEO",
            "Додавати контекстну інформацію про товар"
        ])
        
        return recommendations
    
    def generate_optimal_alt_texts(self, product=None, category=None, image_type=None) -> Dict[str, str]:
        """Генерирует оптимальные alt-тексты для разных типов изображений"""
        
        alt_templates = {
            'product_main': {
                'template': "{product_title} - {color} {product_type} TwoComms",
                'description': "Головне зображення товару"
            },
            'product_gallery': {
                'template': "{product_title} - {color} {product_type} - фото {photo_number}",
                'description': "Додаткові фото товару"
            },
            'category_icon': {
                'template': "{category_name} іконка - TwoComms",
                'description': "Іконка категорії"
            },
            'category_cover': {
                'template': "{category_name} категорія - TwoComms магазин",
                'description': "Обкладинка категорії"
            },
            'logo': {
                'template': "TwoComms логотип - стріт & мілітарі одяг",
                'description': "Логотип бренду"
            },
            'avatar': {
                'template': "Аватар користувача {username}",
                'description': "Аватар користувача"
            },
            'social_icon': {
                'template': "Вхід через {social_network} - TwoComms",
                'description': "Іконка соціальної мережі"
            }
        }
        
        return alt_templates
    
    def create_seo_alt_strategy(self) -> Dict:
        """Создает SEO стратегию для alt-тегов"""
        
        strategy = {
            'principles': [
                {
                    'title': 'Описовість',
                    'description': 'Alt-текст повинен точно описувати зміст зображення',
                    'examples': [
                        'Футболка "Army Style" чорна - TwoComms',
                        'Худі "Street Rebel" сіре - TwoComms'
                    ]
                },
                {
                    'title': 'SEO оптимізація',
                    'description': 'Включати ключові слова для пошукової оптимізації',
                    'examples': [
                        'Стріт футболка чоловіча чорна - TwoComms',
                        'Мілітарі худі унісекс зелена - TwoComms'
                    ]
                },
                {
                    'title': 'Контекстуальність',
                    'description': 'Враховувати контекст сторінки та товару',
                    'examples': [
                        'Футболка "Urban Camo" - головне фото',
                        'Худі "Military Green" - вид збоку'
                    ]
                },
                {
                    'title': 'Українська мова',
                    'description': 'Використовувати українську мову для локальної SEO',
                    'examples': [
                        'Футболка стріт стиль чоловіча',
                        'Мілітарі одяг український бренд'
                    ]
                }
            ],
            'keyword_strategy': {
                'primary_keywords': [
                    'TwoComms', 'стріт одяг', 'мілітарі одяг',
                    'футболка', 'худі', 'лонгслів'
                ],
                'secondary_keywords': [
                    'чоловічий одяг', 'жіночий одяг', 'унісекс',
                    'чорний', 'білий', 'сірий', 'зелений'
                ],
                'long_tail_keywords': [
                    'стріт футболка чоловіча чорна',
                    'мілітарі худі унісекс зелена',
                    'ексклюзивний дизайн TwoComms'
                ]
            },
            'content_guidelines': {
                'length': '5-125 символів',
                'language': 'Українська',
                'tone': 'Описовий, інформативний',
                'avoid': [
                    'Генеричні слова (зображення, фото, картинка)',
                    'Переспам ключових слів',
                    'Занадто довгі описи',
                    'Технічні деталі'
                ]
            },
            'implementation_plan': [
                '1. Аудит поточних alt-тегів',
                '2. Створення шаблонів для різних типів зображень',
                '3. Автоматична генерація alt-текстів',
                '4. Ручна оптимізація критичних зображень',
                '5. Тестування та моніторинг'
            ]
        }
        
        return strategy


def main():
    """Основная функция для запуска анализа"""
    analyzer = AltTagsSEOAnalyzer()
    
    print("🔍 Аналіз alt-тегів TwoComms...")
    
    # Проводим анализ
    analysis = analyzer.analyze_current_alt_tags()
    
    # Создаем стратегию
    strategy = analyzer.create_seo_alt_strategy()
    
    # Сохраняем результаты
    results = {
        'analysis': analysis,
        'strategy': strategy,
        'timestamp': str(Path().cwd())
    }
    
    output_file = 'alt_tags_seo_analysis_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Аналіз завершено. Результати збережено в {output_file}")
    print(f"📊 Загальна статистика:")
    print(f"   - Всього зображень: {analysis['total_images']}")
    print(f"   - З alt-текстами: {analysis['images_with_alt']}")
    print(f"   - Без alt-текстів: {analysis['images_without_alt']}")
    print(f"   - Проблемних: {analysis['problematic_alts']}")
    print(f"   - Хороших: {analysis['good_alts']}")
    
    if analysis['issues']:
        print(f"\n⚠️  Знайдено проблем:")
        for issue in analysis['issues'][:5]:  # Показываем первые 5
            print(f"   - {issue}")
        if len(analysis['issues']) > 5:
            print(f"   ... та ще {len(analysis['issues']) - 5} проблем")


if __name__ == '__main__':
    main()
