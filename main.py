from integrations.ollama_client import send_messages
import os
from pathlib import Path
import json
from integrations.swagger_parser import extract_endpoints_swagger2
import glob
# 1. Получаем список всех доступных сервисов(абсолютные пути)

available_services = []
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

        # 4. Получаем абсолютный путь ко всем файлам сервиса
        files_path = os.path.join(service, "**", "*")
        files = glob.glob(files_path, recursive=True)
        # Исключаем файл swagger.json
        files = [f for f in files if not os.path.basename(f) == "swagger.json"]
        
        # 5. Получаем реализацию эндпоинта в исходном коде
        already_checked = []
        prompt = f"""
        Реализация эндпоинта {endpoint["path"]} не найдена в ранее проверенных файлах: {already_checked}.

        Список доступных файлов: {files}

        Задача:
        1. Выбери ОДИН файл из списка, в котором наиболее вероятно наличие реализации эндпоинта {endpoint["path"]}.
        2. Вызови инструмент get_file_contents для получения содержимого выбранного файла.
        3. Проанализируй содержимое строго на наличие реализации эндпоинта {endpoint["path"]}.

        Возможные результаты (ТОЛЬКО ОДИН из них, без лишнего текста):

        А. Если реализация найдена — верни ТОЛЬКО JSON:
        {{
        "found": true,
        "file": "string",
        "method": "string",
        "path": "string",
        "summary": "string",
        "description": "string",
        "parameters": array of objects,
        "requestBody": object or null,
        "responses": object,
        "tags": array of strings,
        "operationId": "string"
        }}

        Б. Если реализация НЕ найдена в файле — верни ТОЛЬКО JSON:
        {{
        "found": false,
        "file": "string",
        "reason": "implementation not found"
        }}

        Запрещено:
        - Любой текст вне JSON
        - Markdown, комментарии, пояснения
        - Выбор более одного файла
        - Предположения о логике
        - Изменение структуры JSON
        """

        system_prompt = """
        Ты — детерминированный анализатор исходного кода для поиска реализации API-эндпоинтов.

        ПРАВИЛА ПОВЕДЕНИЯ:
        1. Ты строго следуешь только инструкциям из пользовательского сообщения (prompt). Никаких собственных интерпретаций.
        2. Ты НЕ объясняешь свои действия, НЕ рассуждаешь вслух, НЕ добавляешь комментарии.
        3. Твой вывод ДОЛЖЕН содержать ТОЛЬКО то, что явно указано в задаче: либо вызов инструмента, либо JSON строго указанной структуры.
        4. Любой текст вне требуемого формата — критическая ошибка.
        5. Запрещено использовать markdown, код-блоки, кавычки вокруг JSON, пояснения.
        6. Ты НЕ выдумываешь данные, не предполагаешь логику, используешь ТОЛЬКО информацию из предоставленного контекста.

        РАБОТА С ИНСТРУМЕНТАМИ:
        7. Если задача требует получить содержимое файла — ты ДОЛЖЕН вызвать инструмент get_file_contents.
        8. Формат вызова инструмента — ТОЛЬКО следующий (ничего больше):
        <tool_call>
        <parameter name="file_path">полный_путь_к_файлу</parameter>
        </tool_call>

        9. Ты вызываешь инструмент ТОЛЬКО ОДИН раз за сообщение и выбираешь ТОЛЬКО ОДИН файл.

        ФОРМАТ ВЫВОДА ПОСЛЕ АНАЛИЗА:
        10. Если реализация найдена — выводишь ТОЛЬКО чистый JSON (без ```json):
        {
        "found": true,
        "file": "полный_путь",
        "method": "GET|POST|...",
        "path": "/path",
        "summary": "строка или null",
        "description": "строка или null",
        "parameters": [],
        "requestBody": {} или null,
        "responses": {},
        "tags": [],
        "operationId": "строка или null"
        }

        11. Если реализация не найдена — выводишь ТОЛЬКО чистый JSON:
        {
        "found": false,
        "file": "полный_путь",
        "reason": "implementation not found"
        }

        12. Никаких других полей, никаких изменений структуры.
        """
        history = []
        
        result = send_messages(prompt, history, system_prompt)
        # while True:

