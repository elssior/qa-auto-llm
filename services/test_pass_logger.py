"""Минимальный pytest плагин: сохраняет прошедшие тесты в один JSON файл (массив).

Поведение:
    - Без опций командной строки
    - Путь фиксированный: logs/passed_tests.json
    - Формат файла: JSON массив объектов
    - Перед каждым прогоном файл очищается (перезаписывается пустым массивом [])
    - Запись на диск выполняется один раз в конце сессии
"""

from pathlib import Path
import json
import sys
import pytest
from _pytest.reports import TestReport

DEFAULT_PASSED_FILE = Path("logs/passed_tests.json")
_passed_records: list[dict] = []
_already_passed_cache: set[str] | None = None


def pytest_configure(config):
    """Инициализация плагина: создаем директорию и очищаем файл."""
    DEFAULT_PASSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Очищаем файл только если НЕ указан --resume
    resume_enabled = getattr(config, 'resume_enabled', False)
    if not resume_enabled:
        try:
            DEFAULT_PASSED_FILE.write_text("[]", encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"[passed-tests-log] failed to init JSON file: {e}\n")


def pytest_runtest_setup(item: pytest.Item):
    """Пропускаем тест, если он уже passed ранее."""
    global _already_passed_cache
    
    # Ленивая загрузка кеша один раз для всей сессии
    if _already_passed_cache is None:
        try:
            if DEFAULT_PASSED_FILE.exists():
                with DEFAULT_PASSED_FILE.open("r", encoding="utf-8") as f:
                    passed_tests = json.load(f)
                _already_passed_cache = {x["nodeid"] for x in passed_tests}
            else:
                _already_passed_cache = set()
        except Exception:
            _already_passed_cache = set()
    
    if item.nodeid in _already_passed_cache:
        pytest.skip(f"Already passed: {item.nodeid}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Записываем прошедшие тесты."""
    outcome = yield
    report: TestReport = outcome.get_result()
    
    if report.when == "call" and report.outcome == "passed":
        record = {
            "test_name": item.name,
            "nodeid": item.nodeid,
            "file": str(item.fspath),
            "outcome": report.outcome,
        }
        _passed_records.append(record)
        resume_enabled = getattr(item.config, 'resume_enabled', False)
        try:
            if resume_enabled:
                if DEFAULT_PASSED_FILE.exists():
                    with DEFAULT_PASSED_FILE.open("r", encoding="utf-8") as f:
                        old_records = json.load(f)
                else:
                    old_records = []
                all_records = old_records + [record]
                DEFAULT_PASSED_FILE.write_text(
                    json.dumps(all_records, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            else:
                DEFAULT_PASSED_FILE.write_text(
                    json.dumps(_passed_records, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
        except Exception as e:
            sys.stderr.write(f"[passed-tests-log] failed to write JSON: {e}\n")


def pytest_sessionfinish(session, exitstatus):
    """Сохраняем все прошедшие тесты в JSON файл."""
    pass