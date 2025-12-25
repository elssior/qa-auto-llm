# Шаг 8.1: Проверка существования файла
def get_step1_check_file_prompt(file_path):
    """Промпт для проверки существования файла через read_file"""
    return f"""
    Проверь существует ли файл:

    ФАЙЛ: {file_path}

    ЗАДАЧА:
    1. Вызови инструмент read_file("{file_path}")
    2. Ответь одним словом: СУЩЕСТВУЕТ или НЕ_СУЩЕСТВУЕТ

    ВАЖНО: Вызови read_file и проверь результат!
    """


# Шаг 8.2: Чтение conftest.py
def get_step2_read_conftest_prompt(conftest_path):
    """Промпт для извлечения фикстур из conftest.py"""
    return f"""
    Прочитай conftest.py и найди фикстуры:

    ФАЙЛ: {conftest_path}

    ЗАДАЧА:
    1. Вызови ТОЛЬКО read_file("{conftest_path}")
    2. Найди все @pytest.fixture
    3. Для каждой фикстуры опиши: имя и назначение

    ФОРМАТ ОТВЕТА:
    ФИКСТУРЫ:
    - api_client: HTTP клиент для запросов к API
    - attach_curl_on_fail: прикрепляет curl команду при падении теста
    - validate_schema: валидация JSON схемы ответа

    ЗАПРЕЩЕНО:
    - НЕ вызывай list_directory!
    - НЕ вызывай другие инструменты!
    - Используй ТОЛЬКО read_file!
    """


# Шаг 8.3: Преобразование кейсов JSON → Python
def get_step3_transform_cases_prompt(json_cases):
    """Промпт для преобразования JSON кейсов в Python кортежи"""
    return f"""
    ЗАДАЧА: Преобразуй JSON → Python кортежи pytest.param

    ВХОДНЫЕ ДАННЫЕ (JSON):
    {json_cases}

    ПРАВИЛА ПРЕОБРАЗОВАНИЯ:
    
    1. Тип → Список:
       type == "positive" → POSITIVE_CASES
       type == "negative" → NEGATIVE_CASES
    
    2. Данные (1-й аргумент):
       - Если body не null → копируй body
       - Если query_params не null → копируй query_params  
       - Если оба null → используй {{}}
       НЕ ПРИДУМЫВАЙ! Копируй СТРОГО из JSON.
    
    3. Статус (2-й аргумент):
       → Копируй expected_status
    
    4. ID (3-й аргумент):
       → "TC-XXX_name" (snake_case, без "description")

    ПРИМЕР:
    JSON:
    [
      {{"id": "TC-001", "type": "positive", "body": null, "query_params": null, "expected_status": 200}},
      {{"id": "TC-002", "type": "negative", "query_params": {{"filter": "x"}}, "expected_status": 400}}
    ]
    
    PYTHON:
    POSITIVE_CASES = [
        pytest.param({{}}, 200, id="TC-001_get_all"),
    ]
    NEGATIVE_CASES = [
        pytest.param({{"filter": "x"}}, 400, id="TC-002_invalid_filter"),
    ]

    ТРЕБОВАНИЯ:
    - ВКЛЮЧИ ВСЕ КЕЙСЫ (не сокращай!)
    - НЕ пиши import/функции/объяснения
    - НАЧНИ с "POSITIVE_CASES = ["

    ФОРМАТ ОТВЕТА:
    POSITIVE_CASES = [...]
    NEGATIVE_CASES = [...]
    
    БЕЗ инструментов, только текст!
    """


# Шаг 8.4: Генерация кода теста
def get_step4_generate_code_prompt(endpoint_path, method, schema, positive_cases, negative_cases, fixtures_info, existing_content=""):
    """Промпт для генерации полного кода теста по шаблону (с возможностью мерджа)"""
    
    merge_instruction = ""
    if existing_content:
        merge_instruction = f"""
    ВАЖНО — СЛИЯНИЕ КОДА:
    Файл уже существует. Проанализируй EXISTING CODE ниже.
    1. ИЗВЛЕКИ все существующие тесты (функции test_*) и их данные (POSITIVE_CASES_*).
    2. СОХРАНИ их в новом коде без изменений!
    3. ДОБАВЬ новые кейсы как НОВЫЕ переменные (например, POSITIVE_CASES_{method}_{endpoint_path.replace('/', '_')}).
    4. ДОБАВЬ новые функции тестов.
    5. НЕ удаляй старые тесты!
    6. Импорты и фикстуры должны быть общими (вверху файла).
    """

    return f"""
    Создай полный код теста (СЛИЯНИЕ):

    EXISTING CODE (ЕСЛИ ЕСТЬ):
    {existing_content}
    
    {merge_instruction}

    НОВЫЕ ДАННЫЕ:
    ENDPOINT: {endpoint_path}
    METHOD: {method}

    SCHEMA:
    {schema}

    POSITIVE_CASES:
    {positive_cases}

    NEGATIVE_CASES:
    {negative_cases}
    
    ДОСТУПНЫЕ ФИКСТУРЫ:
    {fixtures_info}

    ШАБЛОН (используй этот скелет):

    ```python
    import pytest
    from services.conftest import validate_schema

    ENDPOINT = "{endpoint_path}"
    METHOD = "{method}"

    SUCCESS_RESPONSE_SCHEMA = {schema}

    POSITIVE_CASES = {positive_cases}

    NEGATIVE_CASES = {negative_cases}

    @pytest.mark.parametrize("data, expected_status", POSITIVE_CASES)
    def test_{method.lower()}_positive(api_client, attach_curl_on_fail, data, expected_status):
        \"\"\"Позитивные тесты\"\"\"
        with attach_curl_on_fail(ENDPOINT, data, None, METHOD):
            response = api_client.{method.lower()}(ENDPOINT, {"json" if method in ["POST", "PUT", "PATCH"] else "params"}=data)
            assert response.status_code == expected_status
            validate_schema(response.json(), SUCCESS_RESPONSE_SCHEMA)

    @pytest.mark.parametrize("data, expected_status", NEGATIVE_CASES)
    def test_{endpoint_path.strip('/').replace('/', '_')}_negative(api_client, attach_curl_on_fail, data, expected_status):
        \"\"\"Негативные тесты\"\"\"
        with attach_curl_on_fail(ENDPOINT, data, None, METHOD):
            response = api_client.{method.lower()}(ENDPOINT, {"json" if method in ["POST", "PUT", "PATCH"] else "params"}=data)
            assert response.status_code == expected_status
    ```

    ПРАВИЛА:
    1. Для GET/DELETE используй params=data
    2. Для POST/PUT/PATCH используй json=data
    3. НЕ используй body для GET!
    4. Код БЕЗ отступов в начале
    5. ОБЯЗАТЕЛЬНО добавь импорт: from services.conftest import validate_schema
    6. api_client и attach_curl_on_fail - это фикстуры (в аргументы)
    7. validate_schema - это функция (импортируй, НЕ в аргументы)
    
    КРИТИЧЕСКИ ВАЖНО:
    - POSITIVE_CASES и NEGATIVE_CASES уже готовы! Копируй их ТОЧНО как указано выше!
    - НЕ модифицируй кейсы!
    - НЕ добавляй ключи "body", "path", "method", "headers" в data!
    - data - это ТОЛЬКО содержимое для params= или json=

    СТРОГО ЗАПРЕЩЕНО:
    - НЕ создавай @pytest.fixture!
    - НЕ определяй свои функции!
    - НЕ добавляй validate_schema в аргументы теста!
    
    ВЕРНИ ТОЛЬКО КОД БЕЗ ```python и БЕЗ отступов в начале!
    """


# Шаг 8.5: Создание директории
def get_step5_create_dir_prompt(dir_path):
    """Промпт для вызова create_directory"""
    return f"""
    Создай директорию:

    ПУТЬ: {dir_path}

    ЗАДАЧА:
    1. Вызови create_directory("{dir_path}")
    2. Ответь: СОЗДАНО

    ВАЖНО: Вызови инструмент!
    """


# Шаг 8.6: Запись файла
def get_step6_write_file_prompt(file_path, code):
    """Промпт для вызова write_files (всегда перезапись)"""
    return f"""
    Запиши код в файл (ПЕРЕЗАПИСЬ):

    ФАЙЛ: {file_path}
    ДЕЙСТВИЕ: write_files

    КОД:
    {code}

    ЗАДАЧА:
    1. Вызови write_files с двумя аргументами:
       - Путь к файлу: "{file_path}"
       - Содержимое: весь код из блока КОД выше
    2. Ответь: ЗАПИСАНО

    ВАЖНО:
    - Мы перезаписываем файл полностью, так как объединили старые и новые тесты!
    - Вызови инструмент!
    """