#!/usr/bin/env python3
"""
Media Performance Analyzer
Анализирует изображения и медиа файлы на предмет производительности
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from PIL import Image
import mimetypes

class MediaPerformanceAnalyzer:
    def __init__(self, media_root: str):
        self.media_root = media_root
        self.analysis_results = {}
        
    def analyze_images(self) -> Dict[str, Any]:
        """Анализ изображений"""
        image_stats = {
            "total_images": 0,
            "total_size_bytes": 0,
            "formats": {},
            "sizes": {},
            "problematic_images": [],
            "optimization_potential": {}
        }
        
        # Поддерживаемые форматы изображений
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
        
        for root, dirs, files in os.walk(self.media_root):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()
                
                if file_ext in image_extensions:
                    try:
                        image_stats["total_images"] += 1
                        file_size = os.path.getsize(file_path)
                        image_stats["total_size_bytes"] += file_size
                        
                        # Анализ формата
                        if file_ext not in image_stats["formats"]:
                            image_stats["formats"][file_ext] = {"count": 0, "total_size": 0}
                        image_stats["formats"][file_ext]["count"] += 1
                        image_stats["formats"][file_ext]["total_size"] += file_size
                        
                        # Анализ размеров изображения
                        if file_ext != '.svg':  # SVG не анализируем через PIL
                            try:
                                with Image.open(file_path) as img:
                                    width, height = img.size
                                    pixels = width * height
                                    
                                    # Категории размеров
                                    if pixels < 100000:  # < 100K пикселей
                                        size_category = "small"
                                    elif pixels < 1000000:  # < 1M пикселей
                                        size_category = "medium"
                                    elif pixels < 4000000:  # < 4M пикселей
                                        size_category = "large"
                                    else:
                                        size_category = "very_large"
                                    
                                    if size_category not in image_stats["sizes"]:
                                        image_stats["sizes"][size_category] = {"count": 0, "total_size": 0}
                                    image_stats["sizes"][size_category]["count"] += 1
                                    image_stats["sizes"][size_category]["total_size"] += file_size
                                    
                                    # Поиск проблемных изображений
                                    issues = []
                                    
                                    # Слишком большие размеры
                                    if width > 2000 or height > 2000:
                                        issues.append(f"Слишком большое разрешение: {width}x{height}")
                                    
                                    # Слишком большой размер файла
                                    if file_size > 500000:  # > 500KB
                                        issues.append(f"Слишком большой файл: {file_size/1024:.1f}KB")
                                    
                                    # Неоптимальный формат
                                    if file_ext in ['.bmp', '.tiff']:
                                        issues.append(f"Неоптимальный формат: {file_ext}")
                                    
                                    # Отсутствие WebP версии
                                    if file_ext in ['.jpg', '.jpeg', '.png']:
                                        webp_path = file_path.rsplit('.', 1)[0] + '.webp'
                                        if not os.path.exists(webp_path):
                                            issues.append("Отсутствует WebP версия")
                                    
                                    if issues:
                                        image_stats["problematic_images"].append({
                                            "file": file_path,
                                            "size": f"{width}x{height}",
                                            "file_size_kb": round(file_size/1024, 1),
                                            "issues": issues
                                        })
                                        
                            except Exception as e:
                                image_stats["problematic_images"].append({
                                    "file": file_path,
                                    "error": str(e)
                                })
                    
                    except Exception as e:
                        print(f"Ошибка при анализе {file_path}: {e}")
                        continue
        
        # Расчет потенциала оптимизации
        total_size_mb = image_stats["total_size_bytes"] / (1024 * 1024)
        
        # Оценка экономии при конвертации в WebP
        webp_savings = 0
        for ext, data in image_stats["formats"].items():
            if ext in ['.jpg', '.jpeg', '.png']:
                # WebP обычно на 25-35% меньше
                webp_savings += data["total_size"] * 0.3
        
        image_stats["optimization_potential"] = {
            "total_size_mb": round(total_size_mb, 2),
            "webp_savings_mb": round(webp_savings / (1024 * 1024), 2),
            "webp_savings_percent": round(webp_savings / image_stats["total_size_bytes"] * 100, 1) if image_stats["total_size_bytes"] > 0 else 0,
            "compression_savings_mb": round(total_size_mb * 0.2, 2),  # Оценка 20% экономии от сжатия
            "lazy_loading_benefit": "high" if image_stats["total_images"] > 10 else "medium"
        }
        
        return image_stats
    
    def analyze_other_media(self) -> Dict[str, Any]:
        """Анализ других медиа файлов"""
        media_stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "file_types": {},
            "large_files": [],
            "unused_files": []
        }
        
        # Расширения медиа файлов
        media_extensions = {
            '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv',  # Видео
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',  # Аудио
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Документы
            '.zip', '.rar', '.7z', '.tar', '.gz'  # Архивы
        }
        
        for root, dirs, files in os.walk(self.media_root):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()
                
                if file_ext in media_extensions:
                    try:
                        media_stats["total_files"] += 1
                        file_size = os.path.getsize(file_path)
                        media_stats["total_size_bytes"] += file_size
                        
                        # Анализ типов файлов
                        if file_ext not in media_stats["file_types"]:
                            media_stats["file_types"][file_ext] = {"count": 0, "total_size": 0}
                        media_stats["file_types"][file_ext]["count"] += 1
                        media_stats["file_types"][file_ext]["total_size"] += file_size
                        
                        # Поиск больших файлов
                        if file_size > 10 * 1024 * 1024:  # > 10MB
                            media_stats["large_files"].append({
                                "file": file_path,
                                "size_mb": round(file_size / (1024 * 1024), 1),
                                "type": file_ext
                            })
                    
                    except Exception as e:
                        print(f"Ошибка при анализе {file_path}: {e}")
                        continue
        
        return media_stats
    
    def analyze_media_usage(self, templates_dir: str) -> Dict[str, Any]:
        """Анализ использования медиа файлов в шаблонах"""
        usage_stats = {
            "referenced_files": set(),
            "unreferenced_files": set(),
            "usage_patterns": {},
            "optimization_opportunities": []
        }
        
        # Собираем все медиа файлы
        all_media_files = set()
        for root, dirs, files in os.walk(self.media_root):
            for file in files:
                all_media_files.add(file)
        
        # Анализируем шаблоны
        if os.path.exists(templates_dir):
            for root, dirs, files in os.walk(templates_dir):
                for file in files:
                    if file.endswith('.html'):
                        template_path = os.path.join(root, file)
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Поиск ссылок на медиа файлы
                        import re
                        media_refs = re.findall(r'["\']([^"\']*\.(?:jpg|jpeg|png|gif|webp|svg|mp4|mp3|pdf))["\']', content, re.IGNORECASE)
                        
                        for ref in media_refs:
                            filename = os.path.basename(ref)
                            usage_stats["referenced_files"].add(filename)
                            
                            # Анализ паттернов использования
                            if 'lazy' in content.lower() and filename in content:
                                usage_stats["usage_patterns"]["lazy_loading"] = usage_stats["usage_patterns"].get("lazy_loading", 0) + 1
                            if 'loading="lazy"' in content and filename in content:
                                usage_stats["usage_patterns"]["native_lazy"] = usage_stats["usage_patterns"].get("native_lazy", 0) + 1
                            if 'srcset' in content and filename in content:
                                usage_stats["usage_patterns"]["responsive"] = usage_stats["usage_patterns"].get("responsive", 0) + 1
        
        # Находим неиспользуемые файлы
        usage_stats["unreferenced_files"] = all_media_files - usage_stats["referenced_files"]
        
        # Конвертируем set в list для JSON сериализации
        usage_stats["referenced_files"] = list(usage_stats["referenced_files"])
        usage_stats["unreferenced_files"] = list(usage_stats["unreferenced_files"])
        
        return usage_stats
    
    def analyze_compression_potential(self) -> Dict[str, Any]:
        """Анализ потенциала сжатия"""
        compression_stats = {
            "images_compression": {},
            "total_savings_potential": 0,
            "recommended_actions": []
        }
        
        # Анализ изображений для сжатия
        for root, dirs, files in os.walk(self.media_root):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()
                
                if file_ext in ['.jpg', '.jpeg', '.png']:
                    try:
                        file_size = os.path.getsize(file_path)
                        
                        with Image.open(file_path) as img:
                            # Проверяем качество JPEG
                            if file_ext in ['.jpg', '.jpeg']:
                                if file_size > 200000:  # > 200KB
                                    compression_stats["recommended_actions"].append({
                                        "file": file_path,
                                        "action": "compress_jpeg",
                                        "current_size_kb": round(file_size/1024, 1),
                                        "potential_savings": "30-50%"
                                    })
                            
                            # Проверяем PNG на возможность конвертации в JPEG
                            elif file_ext == '.png':
                                if img.mode == 'RGB' and file_size > 100000:  # > 100KB
                                    compression_stats["recommended_actions"].append({
                                        "file": file_path,
                                        "action": "convert_to_jpeg",
                                        "current_size_kb": round(file_size/1024, 1),
                                        "potential_savings": "60-80%"
                                    })
                    
                    except Exception as e:
                        continue
        
        return compression_stats
    
    def run_full_analysis(self, templates_dir: str = None) -> Dict[str, Any]:
        """Запуск полного анализа"""
        start_time = time.time()
        
        self.analysis_results = {
            "images": self.analyze_images(),
            "other_media": self.analyze_other_media(),
            "compression_potential": self.analyze_compression_potential(),
            "analysis_time": time.time() - start_time
        }
        
        if templates_dir:
            self.analysis_results["usage"] = self.analyze_media_usage(templates_dir)
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        # Рекомендации по изображениям
        images = self.analysis_results.get("images", {})
        if images.get("total_images", 0) > 0:
            total_size_mb = images.get("optimization_potential", {}).get("total_size_mb", 0)
            if total_size_mb > 10:
                recommendations.append(f"Общий размер изображений {total_size_mb}MB - рекомендуется оптимизация")
            
            webp_savings = images.get("optimization_potential", {}).get("webp_savings_mb", 0)
            if webp_savings > 5:
                recommendations.append(f"Конвертация в WebP сэкономит {webp_savings}MB ({images['optimization_potential']['webp_savings_percent']}%)")
            
            problematic_count = len(images.get("problematic_images", []))
            if problematic_count > 0:
                recommendations.append(f"Найдено {problematic_count} проблемных изображений - требуется оптимизация")
        
        # Рекомендации по другим медиа файлам
        other_media = self.analysis_results.get("other_media", {})
        large_files = other_media.get("large_files", [])
        if large_files:
            recommendations.append(f"Найдено {len(large_files)} больших файлов (>10MB) - рассмотрите сжатие или CDN")
        
        # Рекомендации по использованию
        if "usage" in self.analysis_results:
            usage = self.analysis_results["usage"]
            unreferenced = len(usage.get("unreferenced_files", []))
            if unreferenced > 0:
                recommendations.append(f"Найдено {unreferenced} неиспользуемых медиа файлов - можно удалить")
            
            if usage.get("usage_patterns", {}).get("lazy_loading", 0) == 0:
                recommendations.append("Lazy loading не используется - добавьте для улучшения производительности")
        
        # Рекомендации по сжатию
        compression = self.analysis_results.get("compression_potential", {})
        actions = compression.get("recommended_actions", [])
        if actions:
            recommendations.append(f"Найдено {len(actions)} файлов для оптимизации сжатия")
        
        return recommendations

def main():
    """Основная функция для запуска анализа"""
    media_root = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/media"
    templates_dir = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms_django_theme/templates"
    
    analyzer = MediaPerformanceAnalyzer(media_root)
    results = analyzer.run_full_analysis(templates_dir)
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/Users/zainllw0w/PycharmProjects/TwoComms/media_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("Media Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
