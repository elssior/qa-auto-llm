from utils.ollama_client import send_messages, set_debug
import os
from pathlib import Path
import json
from utils.swagger_parser import extract_endpoints_swagger2
import glob
from prompts import search_implementation, merge_results, generate_cases, write_tests
import argparse


def strip_markdown(text: str) -> str:
    """Удаляет markdown-разметку (блоки кода), если она есть, и извлекает содержимое первого блока."""
    text = text.strip()
    if "```" in text:
        # Пытаемся найти начало первого блока
        start_idx = text.find("```")
        # Пропускаем саму метку ``` и возможный идентификатор языка (например, ```json)
        after_start = text[start_idx+3:]
        first_newline = after_start.find("\n")
        if first_newline != -1:
            content_start = start_idx + 3 + first_newline + 1
        else:
            content_start = start_idx + 3
        
        # Ищем конец блока
        end_idx = text.find("```", content_start)
        if end_idx != -1:
            return text[content_start:end_idx].strip()
    return text

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
        
        # Приоритизация файлов: контроллеры, роуты и хендлеры в начало списка
        def file_priority(filepath):
            name = filepath.lower()
            if any(k in name for k in ['route', 'controller', 'handler', 'api', 'rest']):
                return 0
            return 1
        
        files.sort(key=file_priority)
        
        # 5. Получаем реализацию эндпоинта в исходном коде
        system_prompt = search_implementation.SYSTEM_PROMPT
        history = []
        i = 0
        source_code_schema = ""
        
        prompt = search_implementation.get_user_prompt(
            endpoint["method"], 
            endpoint["path"], 
            files, 
            endpoint
        )
        result, all_messages = send_messages(
            prompt, 
            history, 
            system_prompt, 
            step_name="Поиск реализации"
        )

        source_code_schema = strip_markdown(result)

        exit()

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
