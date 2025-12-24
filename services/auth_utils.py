"""
Модуль для работы с авторизацией в системе.
"""

import requests
import json
from qa_constants import SERVICES


def login(username: str, password: str, agent: str = "local") -> str:
    """
    Выполняет авторизацию пользователя и возвращает токен.
    
    Args:
        username (str): Имя пользователя
        password (str): Пароль пользователя
        agent (str): Агент (по умолчанию "local")
    
    Returns:
        str: Токен авторизации (поле 'id' из ответа)
    """
    # Получаем конфигурацию csi-server из общего конфига
    csi_config = SERVICES["csi-server"]
    host = csi_config["host"]
    port = csi_config["port"]
    base_path = csi_config["base_path"]
    
    url = f"http://{host}:{port}{base_path}/users/login"
    
    payload = {
        "username": username,
        "password": password,
        "agent": agent
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url=url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    
    response_data = response.json()
    return response_data['id'] 