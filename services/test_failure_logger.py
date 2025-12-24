"""
Pytest plugin для логирования непройденных тестов.
"""

import logging
from datetime import datetime
from pathlib import Path
import pytest


class TestLoggingConfig:
    """Конфигурация логирования тестов."""
    
    # Основные настройки
    LOG_DIR = "logs"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    @classmethod
    def get_environment_specific_config(cls):
        """Возвращает конфигурацию в зависимости от окружения."""
        return cls


# Создаем глобальный экземпляр конфигурации
logging_config = TestLoggingConfig.get_environment_specific_config()


_failure_logger = None


def pytest_configure(config):
    """Инициализация логгера."""
    global _failure_logger
    
    log_dir = Path(logging_config.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"failed_tests_{timestamp}.log"
    
    logger = logging.getLogger("test_failure_logger")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt=logging_config.DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    
    _failure_logger = logger


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Логирует ошибки и падения тестов."""
    outcome = yield
    report = outcome.get_result()

    if report.failed and _failure_logger:
        test_name = item.name
        test_file = str(item.fspath)
        traceback = getattr(report, 'longreprtext', '')
        stage = report.when.upper()  # CALL, SETUP, TEARDOWN
        message = f"{stage} FAILED: {test_name} in {test_file}\n{traceback}"
        _failure_logger.error(message)