SYSTEM_PROMPT = """
Ты — эксперт по интеграции данных API. Твоя задача: объединить данные из Swagger и исходного кода в полную спецификацию эндпоинта.

ЦЕЛЬ: Создать ПОЛНОЕ описание эндпоинта в формате Swagger 2.0 JSON.

ЧТО ПОЛУЧАЕШЬ:
1. SWAGGER DATA - базовая информация из swagger.json (может быть неполной)
2. SOURCE CODE ANALYSIS - детальная информация из исходного кода (в текстовом формате)

ФОРМАТ ОТВЕТА (только JSON, БЕЗ markdown):

{
  "method": "<HTTP метод>",
  "path": "<путь эндпоинта>",
  "summary": "<краткое описание>",
  "description": "<полное описание>",
  "responses": {
    "200": {
      "description": "<описание ответа>",
      "schema": {
        "type": "<object или array>",
        "properties": {
          "field_name": {
            "type": "<тип>",
            "description": "<описание>"
          }
        }
      }
    }
  }
}

КРИТИЧЕСКИ ВАЖНО:
1. ЗАПРЕЩЕНО использовать $ref - разверни все ссылки в полные объекты
2. Если SOURCE CODE содержит поля в формате "name: type | description" - преобразуй в JSON
3. Для вложенных полей (services[].name) создай вложенную структуру
4. Для enum (state: enum | good,bad) создай {"type": "string", "enum": ["good", "bad"]}
5. ТОЛЬКО JSON в ответе, без ```json и прочего
6. Приоритет: код > swagger (если есть противоречия)
"""

def get_user_prompt(endpoint_swagger, source_code_schema):
    return f"""
    Объедини данные в один Swagger 2.0 JSON:

    SWAGGER DATA (базовая информация):
    {endpoint_swagger}

    SOURCE CODE ANALYSIS (детальная информация из кода):
    {source_code_schema}

    ИНСТРУКЦИИ:
    1. Распарси SOURCE CODE ANALYSIS (текстовый формат):
    - STATUS, FILE, CODE_EVIDENCE, SUMMARY, DESCRIPTION
    - RESPONSE_CODE, RESPONSE_DESCRIPTION, SCHEMA_TYPE
    - SCHEMA_FIELDS в формате "field: type | description"

    2. Объедини с SWAGGER DATA:
    - Используй method и path из SWAGGER
    - Дополни summary, description из SOURCE CODE
    - Создай schema из SCHEMA_FIELDS

    3. Преобразуй SCHEMA_FIELDS в JSON properties:
    ПРИМЕР:
    name: string | Service name
    → "name": {{"type": "string", "description": "Service name"}}
    
    state: enum | Service state | good,bad
    → "state": {{"type": "string", "enum": ["good", "bad"], "description": "Service state"}}
    
    services[]: object | Service object
    → "services": {{"type": "array", "items": {{"type": "object", "properties": {{...}}}}}}

    4. Верни ТОЛЬКО JSON, без ```json
    """
