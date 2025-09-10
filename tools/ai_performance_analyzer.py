#!/usr/bin/env python3
"""
AI Performance Analyzer
Использует OpenAI для дополнительного анализа производительности
"""

import os
import json
import time
import openai
from typing import Dict, List, Any
from pathlib import Path

class AIPerformanceAnalyzer:
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        self.analysis_results = {}
        
    def analyze_code_quality(self, file_path: str, file_content: str) -> Dict[str, Any]:
        """Анализ качества кода с помощью AI"""
        if not self.openai_api_key:
            return {"error": "OpenAI API key not provided"}
        
        try:
            prompt = f"""
            Проанализируй следующий код на предмет производительности и качества:
            
            Файл: {file_path}
            
            Код:
            {file_content[:4000]}  # Ограничиваем размер для API
            
            Пожалуйста, предоставь анализ в следующем формате JSON:
            {{
                "performance_issues": [
                    {{
                        "line": номер_строки,
                        "issue": "описание_проблемы",
                        "severity": "high|medium|low",
                        "suggestion": "рекомендация_по_исправлению"
                    }}
                ],
                "optimization_opportunities": [
                    {{
                        "type": "тип_оптимизации",
                        "description": "описание",
                        "potential_improvement": "ожидаемое_улучшение"
                    }}
                ],
                "code_quality_score": число_от_1_до_10,
                "overall_recommendations": ["рекомендация1", "рекомендация2"]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу производительности веб-приложений. Анализируй код и предоставляй конкретные рекомендации по оптимизации."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            # Парсинг ответа
            ai_response = response.choices[0].message.content
            
            # Попытка извлечь JSON из ответа
            try:
                # Ищем JSON в ответе
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    return {"raw_response": ai_response}
            except json.JSONDecodeError:
                return {"raw_response": ai_response}
                
        except Exception as e:
            return {"error": f"OpenAI API error: {str(e)}"}
    
    def analyze_css_with_ai(self, css_file_path: str) -> Dict[str, Any]:
        """Анализ CSS с помощью AI"""
        try:
            with open(css_file_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Берем первые 3000 символов для анализа
            css_sample = css_content[:3000]
            
            prompt = f"""
            Проанализируй следующий CSS код на предмет производительности:
            
            {css_sample}
            
            Пожалуйста, предоставь анализ в JSON формате:
            {{
                "css_issues": [
                    {{
                        "type": "тип_проблемы",
                        "description": "описание",
                        "severity": "high|medium|low",
                        "fix": "как_исправить"
                    }}
                ],
                "optimization_suggestions": [
                    {{
                        "suggestion": "предложение",
                        "impact": "влияние_на_производительность"
                    }}
                ],
                "performance_score": число_от_1_до_10,
                "critical_issues": ["критическая_проблема1", "критическая_проблема2"]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по CSS оптимизации. Анализируй CSS код на предмет производительности, селекторов, и лучших практик."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content
            
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    return {"raw_response": ai_response}
            except json.JSONDecodeError:
                return {"raw_response": ai_response}
                
        except Exception as e:
            return {"error": f"CSS analysis error: {str(e)}"}
    
    def analyze_javascript_with_ai(self, js_file_path: str) -> Dict[str, Any]:
        """Анализ JavaScript с помощью AI"""
        try:
            with open(js_file_path, 'r', encoding='utf-8') as f:
                js_content = f.read()
            
            # Берем первые 3000 символов для анализа
            js_sample = js_content[:3000]
            
            prompt = f"""
            Проанализируй следующий JavaScript код на предмет производительности:
            
            {js_sample}
            
            Пожалуйста, предоставь анализ в JSON формате:
            {{
                "js_issues": [
                    {{
                        "type": "тип_проблемы",
                        "description": "описание",
                        "severity": "high|medium|low",
                        "line_hint": "примерная_строка_или_паттерн"
                    }}
                ],
                "performance_bottlenecks": [
                    {{
                        "bottleneck": "узкое_место",
                        "impact": "влияние_на_производительность",
                        "solution": "решение"
                    }}
                ],
                "optimization_opportunities": [
                    {{
                        "opportunity": "возможность_оптимизации",
                        "potential_gain": "потенциальная_выгода"
                    }}
                ],
                "performance_score": число_от_1_до_10,
                "memory_concerns": ["проблема_памяти1", "проблема_памяти2"]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по JavaScript оптимизации. Анализируй JS код на предмет производительности, утечек памяти, и лучших практик."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content
            
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    return {"raw_response": ai_response}
            except json.JSONDecodeError:
                return {"raw_response": ai_response}
                
        except Exception as e:
            return {"error": f"JavaScript analysis error: {str(e)}"}
    
    def analyze_django_views_with_ai(self, views_file_path: str) -> Dict[str, Any]:
        """Анализ Django views с помощью AI"""
        try:
            with open(views_file_path, 'r', encoding='utf-8') as f:
                views_content = f.read()
            
            # Берем первые 4000 символов для анализа
            views_sample = views_content[:4000]
            
            prompt = f"""
            Проанализируй следующий Django views код на предмет производительности:
            
            {views_sample}
            
            Пожалуйста, предоставь анализ в JSON формате:
            {{
                "django_issues": [
                    {{
                        "type": "тип_проблемы",
                        "description": "описание",
                        "severity": "high|medium|low",
                        "view_function": "имя_функции_или_класса"
                    }}
                ],
                "database_optimization": [
                    {{
                        "issue": "проблема_с_БД",
                        "solution": "решение",
                        "impact": "влияние_на_производительность"
                    }}
                ],
                "caching_opportunities": [
                    {{
                        "view": "имя_view",
                        "caching_type": "тип_кэширования",
                        "benefit": "выгода"
                    }}
                ],
                "security_concerns": [
                    {{
                        "concern": "проблема_безопасности",
                        "severity": "high|medium|low"
                    }}
                ],
                "performance_score": число_от_1_до_10,
                "n_plus_one_risks": ["риск1", "риск2"]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по Django оптимизации. Анализируй Django views на предмет производительности, N+1 проблем, кэширования и безопасности."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content
            
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    return {"raw_response": ai_response}
            except json.JSONDecodeError:
                return {"raw_response": ai_response}
                
        except Exception as e:
            return {"error": f"Django views analysis error: {str(e)}"}
    
    def generate_comprehensive_recommendations(self, all_analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация комплексных рекомендаций на основе всех данных анализа"""
        if not self.openai_api_key:
            return {"error": "OpenAI API key not provided"}
        
        try:
            # Подготавливаем сводку всех данных анализа
            analysis_summary = {
                "css_analysis": all_analysis_data.get("css_analysis", {}),
                "js_analysis": all_analysis_data.get("js_analysis", {}),
                "django_analysis": all_analysis_data.get("django_analysis", {}),
                "media_analysis": all_analysis_data.get("media_analysis", {}),
                "network_analysis": all_analysis_data.get("network_analysis", {})
            }
            
            prompt = f"""
            На основе следующего комплексного анализа производительности веб-сайта, предоставь детальные рекомендации:
            
            {json.dumps(analysis_summary, indent=2, ensure_ascii=False)[:6000]}
            
            Пожалуйста, предоставь анализ в JSON формате:
            {{
                "priority_issues": [
                    {{
                        "issue": "критическая_проблема",
                        "priority": "critical|high|medium|low",
                        "impact": "влияние_на_производительность",
                        "effort": "low|medium|high",
                        "solution": "детальное_решение"
                    }}
                ],
                "optimization_roadmap": [
                    {{
                        "phase": "фаза_оптимизации",
                        "tasks": ["задача1", "задача2"],
                        "expected_improvement": "ожидаемое_улучшение",
                        "time_estimate": "оценка_времени"
                    }}
                ],
                "performance_metrics": {{
                    "current_score": число_от_1_до_10,
                    "potential_score": число_от_1_до_10,
                    "main_bottlenecks": ["узкое_место1", "узкое_место2"],
                    "quick_wins": ["быстрая_победа1", "быстрая_победа2"]
                }},
                "technical_debt": [
                    {{
                        "debt_type": "тип_техдолга",
                        "description": "описание",
                        "refactoring_priority": "high|medium|low"
                    }}
                ],
                "monitoring_recommendations": [
                    {{
                        "metric": "метрика_для_мониторинга",
                        "tool": "инструмент",
                        "frequency": "частота_проверки"
                    }}
                ]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты ведущий эксперт по оптимизации производительности веб-приложений. Анализируй данные и предоставляй практические, приоритизированные рекомендации."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2500,
                temperature=0.2
            )
            
            ai_response = response.choices[0].message.content
            
            try:
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
                else:
                    return {"raw_response": ai_response}
            except json.JSONDecodeError:
                return {"raw_response": ai_response}
                
        except Exception as e:
            return {"error": f"Comprehensive analysis error: {str(e)}"}
    
    def run_full_analysis(self, project_root: str, analysis_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Запуск полного AI анализа"""
        start_time = time.time()
        
        if not self.openai_api_key:
            return {"error": "OpenAI API key not provided"}
        
        self.analysis_results = {
            "ai_analysis": {},
            "analysis_time": 0
        }
        
        # Анализ основных файлов
        css_file = os.path.join(project_root, "twocomms_django_theme", "static", "css", "styles.css")
        js_file = os.path.join(project_root, "staticfiles", "js", "main.js")
        views_file = os.path.join(project_root, "storefront", "views.py")
        
        if os.path.exists(css_file):
            print("Анализирую CSS с помощью AI...")
            self.analysis_results["ai_analysis"]["css"] = self.analyze_css_with_ai(css_file)
        
        if os.path.exists(js_file):
            print("Анализирую JavaScript с помощью AI...")
            self.analysis_results["ai_analysis"]["javascript"] = self.analyze_javascript_with_ai(js_file)
        
        if os.path.exists(views_file):
            print("Анализирую Django views с помощью AI...")
            self.analysis_results["ai_analysis"]["django_views"] = self.analyze_django_views_with_ai(views_file)
        
        # Генерация комплексных рекомендаций
        if analysis_data:
            print("Генерирую комплексные рекомендации с помощью AI...")
            self.analysis_results["ai_analysis"]["comprehensive_recommendations"] = self.generate_comprehensive_recommendations(analysis_data)
        
        self.analysis_results["analysis_time"] = time.time() - start_time
        
        return self.analysis_results
    
    def generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе AI анализа"""
        recommendations = []
        
        ai_analysis = self.analysis_results.get("ai_analysis", {})
        
        # Рекомендации по CSS
        css_analysis = ai_analysis.get("css", {})
        if "critical_issues" in css_analysis:
            recommendations.extend([f"CSS: {issue}" for issue in css_analysis["critical_issues"]])
        
        # Рекомендации по JavaScript
        js_analysis = ai_analysis.get("javascript", {})
        if "memory_concerns" in js_analysis:
            recommendations.extend([f"JS: {concern}" for concern in js_analysis["memory_concerns"]])
        
        # Рекомендации по Django
        django_analysis = ai_analysis.get("django_views", {})
        if "n_plus_one_risks" in django_analysis:
            recommendations.extend([f"Django: {risk}" for risk in django_analysis["n_plus_one_risks"]])
        
        # Комплексные рекомендации
        comprehensive = ai_analysis.get("comprehensive_recommendations", {})
        if "quick_wins" in comprehensive:
            recommendations.extend([f"Quick Win: {win}" for win in comprehensive["quick_wins"]])
        
        return recommendations

def main():
    """Основная функция для запуска AI анализа"""
    project_root = "/Users/zainllw0w/PycharmProjects/TwoComms/twocomms"
    
    # Проверяем наличие API ключа
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Предупреждение: OPENAI_API_KEY не установлен. AI анализ будет пропущен.")
        return
    
    analyzer = AIPerformanceAnalyzer(api_key)
    
    # Загружаем данные предыдущих анализов
    analysis_files = [
        "css_performance_analysis.json",
        "js_performance_analysis.json", 
        "django_performance_analysis.json",
        "media_performance_analysis.json",
        "network_performance_analysis.json"
    ]
    
    analysis_data = {}
    for file in analysis_files:
        file_path = os.path.join("/Users/zainllw0w/PycharmProjects/TwoComms", file)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                analysis_data[file.replace('_performance_analysis.json', '_analysis')] = json.load(f)
    
    results = analyzer.run_full_analysis(project_root, analysis_data)
    recommendations = analyzer.generate_recommendations()
    
    # Сохранение результатов
    output_file = "/Users/zainllw0w/PycharmProjects/TwoComms/ai_performance_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_results": results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }, f, indent=2, ensure_ascii=False)
    
    print("AI Performance Analysis completed!")
    print(f"Results saved to: {output_file}")
    print(f"Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

if __name__ == "__main__":
    main()
