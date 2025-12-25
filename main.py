from utils.ollama_client import send_messages, set_debug
from utils.console import *
from utils.text_utils import strip_markdown
import os
from pathlib import Path
import json
from utils.swagger_parser import extract_endpoints_swagger2
import glob
from prompts import search_implementation, merge_results, generate_cases, write_tests
import argparse


# Парсинг аргументов командной строки
parser = argparse.ArgumentParser(description="API Test Generator")
parser.add_argument("--debug", action="store_true", help="Включить подробный вывод")
args = parser.parse_args()

# Установка режима отладки
set_debug(args.debug)

# Глобальный кеш для conftest
cached_fixtures_info = None

# 1. Получаем список всех доступных сервисов(абсолютные пути)
print_step(1, "Получение списка сервисов") # ... (существующий код)

source_codes_path = os.path.join(os.path.dirname(__file__), "source_codes")

# Автоматическое создание директории source_codes
if not os.path.exists(source_codes_path):
    os.makedirs(source_codes_path)
    print_warning(f"Создана директория: {source_codes_path}")
    print_info("Поместите в неё папки с сервисами (исходный код + swagger.json)")
services = [p for p in Path(source_codes_path).iterdir() if p.is_dir()]

# 2. Парсим swagger.json
print_step(2, "Парсинг swagger.json")
for service in services:
    swagger_path = os.path.join(service, "swagger.json")
    with open(swagger_path, "r") as f:
        swagger = json.load(f)

    # 3. Получаем список эндпоинтов
    print_step(3, "Получение списка эндпоинтов")
    endpoints = extract_endpoints_swagger2(swagger)
    
    for endpoint in endpoints:
        print_header(f"{endpoint['method']} {endpoint['path']}")
 
        # 4. Получаем абсолютный путь ко всем файлам сервиса
        print_step(4, "Получение списка файлов")
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
        print_step(5, "Получение реализации эндпоинта")

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
                
                print_success("Реализация найдена!")
                code_evidence_str = data['code_evidence']
                print_info(f"Код: {code_evidence_str[:80]}...")
                
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
                    print_info(f"Файл {os.path.basename(removed_file)} удалён (fallback). Осталось: {len(files)}")
                continue

        if not source_code_schema:
            print(f"Прекращение обработки эндпоинта {endpoint['path']} после 10 попыток.")
            continue
        
        # 6. Объединяем результаты в один JSON
        print_step(6, "Объединение результатов")
        prompt = merge_results.get_user_prompt(endpoint, source_code_schema)

        system_prompt = merge_results.SYSTEM_PROMPT

        merged_schema, _ = send_messages(
            prompt, 
            system_prompt=system_prompt, 
            use_tools=False,
            step_name="Объединение результатов (Swagger + Code)"
        )
        merged_schema = strip_markdown(merged_schema)

        # 7. Генерируем кейсы
        print_step(7, "Генерация тестовых кейсов")
        prompt = generate_cases.get_user_prompt(merged_schema)

        system_prompt = generate_cases.SYSTEM_PROMPT

        gen_cases, _ = send_messages(
            prompt, 
            system_prompt=system_prompt, 
            use_tools=False,
            step_name="Генерация тестовых кейсов"
        )
        gen_cases = strip_markdown(gen_cases)

        # 8. Формируем файл с тестами (6 подшагов)
        root_path_services = os.path.join(os.path.dirname(__file__), "services")
        service_test_dir = os.path.join(root_path_services, service.name)
        
        endpoint_filename = endpoint['path'].strip('/').replace('/', '_') or "root"
        full_path_endpoint = os.path.join(service_test_dir, f"{endpoint_filename}.py")

        print_step(8, "Создание файла тестов")
        print_info(f"Файл: {full_path_endpoint}")

        # 8.1 Проверка существования файла
        print_substep("8.1", "Проверка файла")
        prompt = write_tests.get_step1_check_file_prompt(full_path_endpoint)
        result, _ = send_messages(prompt, step_name="Проверка файла")
        file_exists = result.upper().strip().rstrip('.!?') == "СУЩЕСТВУЕТ"  # Точная проверка (игнорируем знаки препинания)
        existing_content = ""
        
        if file_exists:
            print_warning("Файл уже существует, будем объединять кейсы")
            with open(full_path_endpoint, 'r') as f:
                existing_content = f.read()
        else:
            print_info("Файл не существует, будет создан")

        # 8.2 Чтение conftest.py (с кешированием)
        print_substep("8.2", "Чтение conftest.py")
        conftest_path = os.path.join(root_path_services, "conftest.py")
        
        if cached_fixtures_info:
            fixtures_info = cached_fixtures_info
            print_info("Используем закешированную информацию о фикстурах")
        else:
            prompt = write_tests.get_step2_read_conftest_prompt(conftest_path)
            fixtures_info, _ = send_messages(prompt, step_name="Чтение conftest")
            cached_fixtures_info = fixtures_info
            print_success("Фикстуры найдены и закешированы")

        # 8.3 Преобразование кейсов JSON → Python
        print_substep("8.3", "Преобразование кейсов JSON → Python")
        prompt = write_tests.get_step3_transform_cases_prompt(gen_cases)
        result, _ = send_messages(prompt, use_tools=False, step_name="Преобразование кейсов")
        cases_code = strip_markdown(result)
        
        
        # Парсим POSITIVE_CASES и NEGATIVE_CASES
        positive_cases = "[]"
        negative_cases = "[]"
        if "POSITIVE_CASES" in cases_code:
            start = cases_code.find("POSITIVE_CASES = ")
            if start != -1:
                end = cases_code.find("\n\nNEGATIVE_CASES", start)
                if end == -1:
                    end = cases_code.find("\nNEGATIVE_CASES", start)
                if end != -1:
                    positive_cases = cases_code[start:end].replace("POSITIVE_CASES = ", "").strip()
        
        if "NEGATIVE_CASES" in cases_code:
            start = cases_code.find("NEGATIVE_CASES = ")
            if start != -1:
                negative_cases = cases_code[start:].replace("NEGATIVE_CASES = ", "").strip()
        
        # Валидация: проверка количества кейсов
        try:
            json_cases = json.loads(gen_cases)
            json_count = len(json_cases)
            python_count = positive_cases.count("pytest.param") + negative_cases.count("pytest.param")
            
            if python_count < json_count:
                print_warning(f"Модель потеряла кейсы! JSON: {json_count}, Python: {python_count}")
            elif python_count == json_count:
                print_success(f"Все {json_count} кейсов преобразованы корректно")
            else:
                print_info(f"Кейсов: JSON={json_count}, Python={python_count}")
        except Exception as e:
            print_warning(f"Не удалось проверить количество кейсов: {e}")
        
        print_success("Кейсы преобразованы")

        # 8.4 Генерация кода теста
        print_substep("8.4", "Генерация кода теста")
        
        # merged_schema это строка JSON, нужно распарсить
        try:
            merged_schema_dict = json.loads(merged_schema)
            schema_json = json.dumps(merged_schema_dict.get('responses', {}).get('200', {}).get('schema', {}))
        except json.JSONDecodeError:
            print(f"  [ERROR] Не удалось распарсить merged_schema как JSON")
            schema_json = "{}"
        
        prompt = write_tests.get_step4_generate_code_prompt(
            endpoint['path'],
            endpoint.get('method', 'GET'),
            schema_json,
            positive_cases,
            negative_cases,
            fixtures_info,
            existing_content
        )
        result, _ = send_messages(prompt, use_tools=False, step_name="Генерация кода")
        
        # Убираем markdown разметку (включая dedent)
        test_code = strip_markdown(result)
        
        # autopep8 для базового PEP8 форматирования (без агрессивных изменений)
        try:
            import autopep8
            original_code = test_code
            test_code = autopep8.fix_code(test_code)  # Без aggressive - только базовые исправления
            
            if test_code != original_code:
                print_info("Код отформатирован (autopep8)")
        except Exception as e:
            print_warning(f"autopep8: {e}")
        
        test_code = test_code.strip()

        
        print_success(f"Код сгенерирован ({len(test_code)} символов)")

        # 8.5 Валидация синтаксиса Python
        print_substep("8.5", "Валидация синтаксиса Python")
        try:
            compile(test_code, '<string>', 'exec')
            print_success("Код валидный")
        except SyntaxError as e:
            print_error(f"Синтаксическая ошибка: {e}")
            print_warning("Пропускаем создание файла")
            continue

        # 8.5.1 Проверка на потерю тестов (Safety Check)
        if file_exists and existing_content:
            old_tests_count = existing_content.count("def test_")
            new_tests_count = test_code.count("def test_")
            
            if new_tests_count < old_tests_count:
                print_error(f"ОПАСНОСТЬ: Модель потеряла тесты! Было: {old_tests_count}, Стало: {new_tests_count}")
                print_warning("Файл НЕ будет перезаписан для безопасности.")
                continue
            
            print_success(f"Количество тестов: {old_tests_count} -> {new_tests_count}")

        # 8.6 Запись файла
        print_substep("8.6", "Запись файла")
        
        # Создать директорию если нужно
        if not file_exists:
            os.makedirs(os.path.dirname(full_path_endpoint), exist_ok=True)
            print_info(f"Директория создана: {os.path.basename(os.path.dirname(full_path_endpoint))}")
        
        # Записать файл НАПРЯМУЮ (без LLM, чтобы не портить код)
        with open(full_path_endpoint, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        print_success(f"Файл с тестами {'обновлён' if file_exists else 'создан'}!")
        print_info(f"Путь: {full_path_endpoint}")
