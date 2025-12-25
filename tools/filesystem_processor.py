from typing import List
import os
from pathlib import Path
from pydantic_ai import Agent
from utils.console import print_tool_call

def read_file(path: str) -> str:
    """Читает содержимое файла по указанному пути. Возвращает текст файла или сообщение об ошибке."""
    print_tool_call("read_file", os.path.basename(path))
    try:
        with open(path, "r", encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"

def write_files(path: str, contents: str) -> str:
    """Записывает переданное содержимое в файл. Если папки не существуют, они будут созданы."""
    print_tool_call("write_files", os.path.basename(path))
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding='utf-8') as f:
            f.write(contents)
        return f"Successfully written to {path}"
    except Exception as e:
        return f"Error writing to {path}: {str(e)}"

def append_file(path: str, contents: str) -> str:
    """Добавляет содержимое в конец существующего файла."""
    print_tool_call("append_file", os.path.basename(path))
    try:
        with open(path, "a", encoding='utf-8') as f:
            f.write(contents)
        return f"Successfully appended to {path}"
    except Exception as e:
        return f"Error appending to {path}: {str(e)}"

def check_exists(path: str) -> bool:
    """Проверяет существование файла или директории по указанному пути."""
    print_tool_call("check_exists", os.path.basename(path))
    return Path(path).exists()

def list_directory(path: str) -> List[str]:
    """Возвращает список всех файлов и подпапок в указанной директории."""
    print_tool_call("list_directory", os.path.basename(path))
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return [f"Error: Path {path} does not exist"]
        if not dir_path.is_dir():
            return [f"Error: Path {path} is not a directory"]
        return [str(p) for p in dir_path.iterdir()]
    except Exception as e:
        return [f"Error listing directory {path}: {str(e)}"]

def create_directory(path: str) -> str:
    """Создает директорию (и все промежуточные), если они еще не существуют."""
    print_tool_call("create_directory", os.path.basename(path))
    try:
        os.makedirs(path, exist_ok=True)
        return f"Directory {path} created or already exists"
    except Exception as e:
        return f"Error creating directory {path}: {str(e)}"

def register(agent: Agent) -> None:
    agent.tool_plain(read_file)
    agent.tool_plain(write_files)
    agent.tool_plain(check_exists)
    agent.tool_plain(list_directory)
    agent.tool_plain(create_directory)
    agent.tool_plain(append_file)
