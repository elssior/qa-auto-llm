from utils.ollama_client import send_messages, set_debug
import os
from pathlib import Path
import json
from utils.swagger_parser import extract_endpoints_swagger2
import glob
from prompts import search_implementation, merge_results, generate_cases, write_tests
import argparse


def strip_markdown(text):
    """Убирает markdown-разметку из текста."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    return text.strip()


# Парсинг аргументов командной строки
parser = argparse.ArgumentParser(description="API Test Generator")
parser.add_argument("--debug", action="store_true", help="Включить подробный вывод")
args = parser.parse_args()

# Установка режима отладки
set_debug(args.debug)

# 1. Получаем список всех доступных сервисов(абсолютные пути)


source_codes_path = os.path.join(os.path.dirname(__file__), "source_codes")
services = [p for p in Path(source_codes_path).iterdir() if p.is_dir()]

# 2. Парсим swagger.json
for service in services:
    swagger_path = os.path.join(service, "swagger.json")
    with open(swagger_path, "r") as f:
        swagger = json.load(f)

    # 3. Получаем список эндпоинтов
    endpoints = extract_endpoints_swagger2(swagger)
    
    for endpoint in endpoints:
        print(f"\nProcessing endpoint: {endpoint['method']} {endpoint['path']}")
 
         # 4. Получаем абсолютный путь ко всем файлам сервиса
        files_path = os.path.join(service, "**", "*")
        files = glob.glob(files_path, recursive=True)
        # Исключаем файл swagger.json
        files = [f for f in files if not os.path.basename(f) == "swagger.json" and os.path.isfile(f)]
        
        # Фильтруем файлы, оставляя только исходный код
        source_extensions = {'.ml', '.mli', '.py', '.js', '.ts', '.go', '.java', '.c', '.cpp', '.h', '.rs'}
        files = [f for f in files if Path(f).suffix in source_extensions]
        
        # Вспомогательные функции
        def parse_text_response(text):
            """Парсит текстовый ответ модели"""
            lines = text.strip().split('\n')
            data = {'status': None, 'file': None, 'reason': None, 'code_evidence': [], 'schema_fields': []}
            current_section = None
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Простые поля
                for key, prefix in [('status', 'STATUS:'), ('file', 'FILE:'), ('reason', 'REASON:')]:
                    if line_stripped.startswith(prefix):
                        data[key] = line_stripped[len(prefix):].strip()
                        current_section = None
                        break
                else:
                    # Секции с несколькими строками
                    if line_stripped.startswith('CODE_EVIDENCE:'):
                        current_section = 'code'
                    elif line_stripped.startswith('SCHEMA_FIELDS:'):
                        current_section = 'schema'
                    elif current_section == 'code':
                        data['code_evidence'].append(lines[i])
                    elif current_section == 'schema' and line_stripped:
                        data['schema_fields'].append(lines[i])
            
            data['code_evidence'] = '\n'.join(data['code_evidence']).strip()
            data['schema_fields'] = '\n'.join(data['schema_fields']).strip()
            return data
        
        def remove_file(file_path):
            """Удаляет файл из списка и выводит информацию"""
            if file_path and file_path in files:
                files.remove(file_path)
                print(f"  [INFO] Файл {file_path} удалён из списка.")
                print(f"  [INFO] Осталось файлов: {len(files)}")
                return True
            return False
        
        # 5. Получаем реализацию эндпоинта в исходном коде
        source_code_schema = ""
        
        for attempt in range(1, 11):  # Максимум 10 попыток
            prompt = search_implementation.get_user_prompt(endpoint["method"], endpoint["path"], files)
            result, all_messages = send_messages(
                prompt, [], search_implementation.SYSTEM_PROMPT,
                step_name=f"Поиск реализации (попытка {attempt})"
            )
            
            # Проверяем вызов read_file
            tool_called = any(
                hasattr(msg, 'parts') and any(
                    hasattr(part, 'tool_name') and part.tool_name == 'read_file'
                    for part in (msg.parts if hasattr(msg, 'parts') else [])
                )
                for msg in all_messages
            )
            
            if not tool_called:
                print(f"  [WARNING] Модель НЕ вызвала read_file! Пропускаем итерацию.")
                continue
            
            try:
                # Парсим ответ
                data = parse_text_response(result)
                
                # Валидация формата
                if not data['status'] or not data['file']:
                    print(f"  [ERROR] Неверный формат ответа: отсутствует STATUS или FILE")
                    continue
                
                print(f"  [INFO] Файл: {data['file']}")
                
                # NOT_FOUND
                if data['status'] == 'NOT_FOUND':
                    print(f"  [NOT FOUND] Реализация не найдена")
                    if data['reason']:
                        print(f"  [REASON] {data['reason']}")
                    remove_file(data['file'])
                    continue
                
                # Неизвестный статус
                if data['status'] != 'FOUND':
                    print(f"  [ERROR] Неизвестный STATUS: {data['status']}")
                    continue
                
                # FOUND - проверки
                if not data['code_evidence']:
                    print(f"  [ERROR] FOUND, но нет CODE_EVIDENCE")
                    remove_file(data['file'])
                    continue
                
                print(f"  [FOUND] Реализация найдена!")
                print(f"  [EVIDENCE] {data['code_evidence'][:200]}...")
                
                if data['schema_fields']:
                    print(f"  [SCHEMA] {data['schema_fields'][:100]}...")
                
                # СТРОГАЯ проверка: маршрут в code_evidence
                if endpoint['path'] not in data['code_evidence']:
                    print(f"  [REJECT] CODE_EVIDENCE НЕ содержит маршрут {endpoint['path']}!")
                    print(f"  [REJECT] Это галлюцинация - модель процитировала нерелевантный код.")
                    remove_file(data['file'])
                    continue
                
                # Успех!
                source_code_schema = result.strip()
                break
                
            except Exception as e:
                print(f"  [ERROR] Ошибка обработки: {e}")
                
                # Пытаемся извлечь FILE:
                import re
                match = re.search(r'FILE:\s*(.+)', result)
                if match and remove_file(match.group(1).strip()):
                    continue
                
                # Fallback - удаляем первый файл
                if files:
                    removed_file = files.pop(0)
                    print(f"  [WARNING] Не удалось извлечь FILE")
                    print(f"  [INFO] Файл {removed_file} удалён (fallback). Осталось: {len(files)}")
                continue

        if not source_code_schema:
            print(f"Прекращение обработки эндпоинта {endpoint['path']} после 10 попыток.")
            continue
        
        # 6. Объединяем результаты в один JSON
        prompt = merge_results.get_user_prompt(endpoint, source_code_schema)

        system_prompt = merge_results.SYSTEM_PROMPT

        merged_schema, _ = send_messages(
            prompt, 
            system_prompt=system_prompt, 
            use_tools=False,
            step_name="Объединение результатов (Swagger + Code)"
        )
        merged_schema = strip_markdown(merged_schema)

        exit()

        # 7. Генерируем кейсы
        prompt = generate_cases.get_user_prompt(merged_schema)

        system_prompt = generate_cases.SYSTEM_PROMPT

        gen_cases, _ = send_messages(
            prompt, 
            system_prompt=system_prompt, 
            use_tools=False,
            step_name="Генерация тестовых кейсов"
        )
        gen_cases = strip_markdown(gen_cases)
        
        root_path_services = os.path.join(os.path.dirname(__file__), "services")
        service_test_dir = os.path.join(root_path_services, service.name)
        
        endpoint_filename = endpoint['path'].strip('/').replace('/', '_') or "root"
        full_path_endpoint = os.path.join(service_test_dir, f"{endpoint_filename}.py")
        
        # 8. Формируем файл с тестами
        system_prompt = write_tests.SYSTEM_PROMPT
 
        prompt = write_tests.get_user_prompt(full_path_endpoint, root_path_services, gen_cases)

        history = []
        max_attempts = 20  # Максимум 20 попыток для защиты от бесконечного цикла
        i = 0
        
        while i < max_attempts:
            result, all_messages = send_messages(
                prompt, 
                history=history, 
                system_prompt=system_prompt,
                step_name=f"Создание файла тестов (попытка {i+1})"
            )
            history = all_messages
            clean_result = result.strip()

            if clean_result.upper() == "DONE":
                break
            
            i += 1
