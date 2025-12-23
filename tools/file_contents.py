from typing import List
import os
from pydantic_ai import Agent

def register(agent: Agent) -> None:
    @agent.tool_plain
    def get_file_contents(path: str) -> str:
        """Возвращает содержимое файла"""
        print(f"Получаем содержимое файла: {path}")
        try:
            with open(path, "r", encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"