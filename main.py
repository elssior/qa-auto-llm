from integrations.ollama_client import send_messages
import os
from pathlib import Path
import json
from integrations.swagger_parser import extract_endpoints_swagger2

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
        print(endpoint)

    
        