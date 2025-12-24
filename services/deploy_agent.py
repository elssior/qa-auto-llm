#!/usr/bin/env python3
"""
Утилита для автоматического развертывания mirada-agent на удаленном хосте.

Функционал:
- Копирование папки mirada-agent на указанный хост через SCP
- Исключение служебных папок и кэшей
- Проверка доступности SSH ключей

Использование:
    python services/deploy_agent.py --mirada-host=192.168.1.100
    python services/deploy_agent.py --mirada-host=192.168.1.100 --verbose
"""

import os
import sys
import subprocess
import tempfile
import shutil
import argparse
import logging
import time
import platform
from pathlib import Path
from typing import List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Определяем платформу
IS_WINDOWS = platform.system() == "Windows"

class AgentDeployManager:
    """Менеджер для развертывания mirada-agent на удаленном хосте."""
    
    # Списки файлов и папок для исключения
    EXCLUDE_PATTERNS = [
        # Служебные папки Python
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.pytest_cache',
        '.benchmarks',
        
        # Папки IDE и редакторов
        '.vscode',
        '.idea',
        '*.swp',
        '*.swo',
        '*~',
        
        # Системные файлы
        '.DS_Store',
        'Thumbs.db',
        'desktop.ini',
        
        # Git и версионный контроль
        '.git',
        '.gitignore',
        '.gitkeep',
        
        # Временные файлы
        '*.tmp',
        '*.temp',
        '*.log',
        '*.bak',
        
        # Файлы окружения
        '.env',
        '.env.local',
        'venv',
        'env',
        
        # Другие служебные файлы
        '*.pid',
        'nohup.out',
    ]
    
    def __init__(self, mirada_host: str):
        """
        Инициализация менеджера развертывания.
        
        Args:
            mirada_host: IP адрес или hostname Mirada хоста
        """
        self.mirada_host = mirada_host
        self.username = "codemaster"
        self.project_root = self._find_project_root()
        self.agent_source_path = self.project_root / "mirada-agent"
        self.remote_path = f"/home/{self.username}/mirada-agent"
        
        logger.info(f"Инициализация развертывания агента")
        logger.info(f"  Источник: {self.agent_source_path}")
        logger.info(f"  Целевой хост: {mirada_host}")
        logger.info(f"  Пользователь: {self.username}")
        logger.info(f"  Удаленный путь: {self.remote_path}")
    
    def _find_project_root(self) -> Path:
        """Находит корневую директорию проекта."""
        current_path = Path(__file__).resolve()
        
        # Ищем вверх по дереву директорий файлы, указывающие на корень проекта
        for parent in current_path.parents:
            if (parent / "mirada-agent").exists() and (parent / "services").exists():
                return parent
        
        # Если не нашли, используем текущую директорию
        return Path.cwd()
    
    def _get_ssh_command(self) -> List[str]:
        """Возвращает базовую SSH команду с правильными параметрами для платформы."""
        ssh_executable = self._find_ssh_executable()
        if not ssh_executable:
            raise RuntimeError(f"SSH клиент не найден на платформе {platform.system()}")
        
        base_cmd = [
            ssh_executable,
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=10'
        ]
        
        if IS_WINDOWS:
            base_cmd.extend(['-o', 'LogLevel=ERROR'])
        else:
            base_cmd.extend(['-o', 'LogLevel=ERROR'])
        
        base_cmd.append(f'{self.username}@{self.mirada_host}')
        return base_cmd
    
    def _find_ssh_executable(self) -> Optional[str]:
        """Находит SSH исполняемый файл на разных платформах."""
        ssh_candidates = []
        
        if IS_WINDOWS:
            ssh_candidates = [
                'ssh',  # Если SSH в PATH
                'C:\\Windows\\System32\\OpenSSH\\ssh.exe',  # Windows 10/11 встроенный SSH
                'C:\\Program Files\\Git\\usr\\bin\\ssh.exe',  # Git for Windows
                'C:\\Program Files (x86)\\Git\\usr\\bin\\ssh.exe',  # Git for Windows 32-bit
            ]
        else:
            ssh_candidates = [
                'ssh',  # Обычно в PATH
                '/usr/bin/ssh',
                '/usr/local/bin/ssh',
            ]
        
        for ssh_path in ssh_candidates:
            try:
                result = subprocess.run([ssh_path, '-V'], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE, 
                                      timeout=5)
                if result.returncode == 0 or b'OpenSSH' in result.stderr:
                    logger.debug(f"Найден SSH клиент: {ssh_path}")
                    return ssh_path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        return None
    
    def _check_ssh_connectivity(self) -> bool:
        """Проверяет SSH подключение к удаленному хосту."""
        try:
            logger.info("Проверка SSH подключения...")
            
            # Команда для проверки подключения
            ssh_cmd = self._get_ssh_command() + ['echo', 'SSH_CONNECTION_TEST']
            
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15
            )
            
            if result.returncode == 0 and b'SSH_CONNECTION_TEST' in result.stdout:
                logger.info("SSH подключение успешно")
                return True
            else:
                logger.error("SSH подключение неуспешно")
                logger.error(f"Код возврата: {result.returncode}")
                logger.error(f"Stderr: {result.stderr.decode()}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут SSH подключения")
            return False
        except Exception as e:
            logger.error(f"Ошибка SSH подключения: {e}")
            return False
    
    def _check_agent_source(self) -> bool:
        """Проверяет наличие исходного кода агента."""
        if not self.agent_source_path.exists():
            logger.error(f"Папка mirada-agent не найдена: {self.agent_source_path}")
            return False
        
        # Проверяем ключевые файлы
        required_files = ["main.py", "requirements.txt"]
        for file_name in required_files:
            file_path = self.agent_source_path / file_name
            if not file_path.exists():
                logger.error(f"Обязательный файл не найден: {file_path}")
                return False
        
        logger.info("Исходный код агента найден")
        return True
    
    def _create_clean_copy(self) -> Path:
        """Создает очищенную копию агента во временной директории."""
        logger.info("Создание очищенной копии агента...")
        
        # Создаем временную директорию
        temp_dir = Path(tempfile.mkdtemp(prefix="mirada_agent_deploy_"))
        target_dir = temp_dir / "mirada-agent"
        
        try:
            # Копируем всю структуру, исключая ненужные файлы
            shutil.copytree(
                self.agent_source_path,
                target_dir,
                ignore=self._create_ignore_function()
            )
            
            logger.info(f"Очищенная копия создана: {target_dir}")
            return target_dir
            
        except Exception as e:
            logger.error(f"Ошибка создания очищенной копии: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def _create_ignore_function(self):
        """Создает функцию для игнорирования файлов при копировании."""
        def ignore_patterns(directory, files):
            ignored = []
            for file in files:
                file_path = Path(directory) / file
                
                # Проверяем каждый паттерн исключения
                for pattern in self.EXCLUDE_PATTERNS:
                    if '*' in pattern:
                        # Обрабатываем wildcard паттерны
                        import fnmatch
                        if fnmatch.fnmatch(file, pattern):
                            ignored.append(file)
                            break
                    else:
                        # Точное совпадение
                        if file == pattern:
                            ignored.append(file)
                            break
                        # Или если это директория
                        elif file_path.is_dir() and file == pattern:
                            ignored.append(file)
                            break
            
            if ignored:
                logger.debug(f"Исключены из {directory}: {ignored}")
            
            return ignored
        
        return ignore_patterns
    
    def _execute_scp(self, local_path: Path) -> bool:
        """Выполняет копирование через SCP."""
        logger.info("Копирование файлов через SCP...")
        
        try:
            # Находим SCP исполняемый файл
            scp_executable = self._find_scp_executable()
            if not scp_executable:
                logger.error(f"SCP не найден на платформе {platform.system()}")
                return False
            
            # Формируем SCP команду
            scp_cmd = [
                scp_executable,
                '-r',  # Рекурсивно
                '-C',  # Сжатие
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'LogLevel=ERROR',
                '-o', 'BatchMode=yes',
                str(local_path),
                f'{self.username}@{self.mirada_host}:/home/{self.username}/'
            ]
            
            logger.info(f"Выполнение команды: {' '.join(scp_cmd)}")
            
            # Выполняем SCP
            result = subprocess.run(
                scp_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 минут таймаут
            )
            
            if result.returncode == 0:
                logger.info("SCP копирование успешно завершено")
                return True
            else:
                logger.error("Ошибка SCP копирования")
                logger.error(f"Код возврата: {result.returncode}")
                logger.error(f"Stderr: {result.stderr.decode()}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут SCP копирования")
            return False
        except Exception as e:
            logger.error(f"Ошибка выполнения SCP: {e}")
            return False
    
    def _find_scp_executable(self) -> Optional[str]:
        """Находит SCP исполняемый файл на разных платформах."""
        scp_candidates = []
        
        if IS_WINDOWS:
            scp_candidates = [
                'scp',  # Если SCP в PATH
                'C:\\Windows\\System32\\OpenSSH\\scp.exe',  # Windows 10/11 встроенный SCP
                'C:\\Program Files\\Git\\usr\\bin\\scp.exe',  # Git for Windows
                'C:\\Program Files (x86)\\Git\\usr\\bin\\scp.exe',  # Git for Windows 32-bit
            ]
        else:
            scp_candidates = [
                'scp',  # Обычно в PATH
                '/usr/bin/scp',
                '/usr/local/bin/scp',
            ]
        
        for scp_path in scp_candidates:
            try:
                result = subprocess.run([scp_path, '-h'], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE, 
                                      timeout=5)
                # SCP обычно возвращает ненулевой код при выводе справки, но это нормально
                if b'usage:' in result.stderr.lower() or b'scp' in result.stderr.lower():
                    logger.debug(f"Найден SCP клиент: {scp_path}")
                    return scp_path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        return None
    
    def _setup_remote_agent(self) -> bool:
        """Настраивает права доступа для файлов агента на удаленном хосте."""
        logger.info("Настройка прав доступа для агента...")
        
        setup_commands = [
            # Делаем все shell скрипты исполняемыми
            f"chmod +x {self.remote_path}/*.sh",
            
            # Конвертируем возможные Windows окончания строк в Unix
            f"cd {self.remote_path} && sed -i 's/\\r$//' *.sh",
        ]
        
        try:
            for cmd in setup_commands:
                logger.info(f"Выполнение: {cmd}")
                
                ssh_cmd = self._get_ssh_command() + [cmd]
                
                result = subprocess.run(
                    ssh_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60
                )
                
                if result.returncode != 0:
                    logger.warning(f"Команда завершилась с кодом {result.returncode}: {cmd}")
                    logger.warning(f"Stderr: {result.stderr.decode()}")
                    # Продолжаем выполнение других команд
                else:
                    logger.debug(f"Команда выполнена успешно: {cmd}")
            
            logger.info("Настройка агента завершена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка настройки агента: {e}")
            return False
    
    def _verify_deployment(self) -> bool:
        """Проверяет успешность развертывания."""
        logger.info("Проверка развертывания...")
        
        try:
            # Проверяем наличие основных файлов на удаленном хосте
            check_cmd = self._get_ssh_command() + [
                f'test -f {self.remote_path}/main.py && test -f {self.remote_path}/requirements.txt && echo "FILES_OK"'
            ]
            
            result = subprocess.run(
                check_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )
            
            if result.returncode == 0 and b'FILES_OK' in result.stdout:
                logger.info("Развертывание успешно проверено")
                return True
            else:
                logger.error("Проверка развертывания неуспешна")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки развертывания: {e}")
            return False
    
    def deploy(self) -> bool:
        """
        Выполняет полное развертывание агента.
            
        Returns:
            bool: True если развертывание успешно
        """
        logger.info("Начало развертывания mirada-agent")
        
        # Шаг 1: Проверка предварительных условий
        if not self._check_agent_source():
            return False
        
        if not self._check_ssh_connectivity():
            logger.error("Убедитесь, что:")
            logger.error("   1. SSH ключи настроены: ssh-copy-id codemaster@<host>")
            logger.error("   2. Хост доступен по сети")
            logger.error("   3. Пользователь существует и имеет права")
            return False
        
        # Шаг 2: Создание очищенной копии
        temp_agent_path = None
        try:
            temp_agent_path = self._create_clean_copy()
            
            # Шаг 3: SCP копирование
            if not self._execute_scp(temp_agent_path):
                return False
            
            # Шаг 4: Настройка на удаленном хосте
            if not self._setup_remote_agent():
                return False
            
            # Шаг 5: Проверка развертывания
            if not self._verify_deployment():
                return False
            
            logger.info("Развертывание mirada-agent успешно завершено!")
            logger.info(f"Агент установлен в: {self.remote_path}")
            logger.info("Для запуска агента выполните:")
            logger.info(f"   ssh {self.username}@{self.mirada_host}")
            logger.info(f"   cd {self.remote_path}")
            logger.info("   sudo ./start.sh")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка развертывания: {e}")
            return False
        
        finally:
            # Очистка временных файлов
            if temp_agent_path and temp_agent_path.parent.exists():
                shutil.rmtree(temp_agent_path.parent, ignore_errors=True)
                logger.debug("Временные файлы очищены")


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Утилита для автоматического развертывания mirada-agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python services/deploy_agent.py --mirada-host=192.168.1.100
  python services/deploy_agent.py --mirada-host=server.example.com --verbose

Требования:
  1. SSH ключи должны быть настроены для беспарольного доступа
  2. Пользователь codemaster должен существовать на удаленном хосте
  3. Пользователь должен иметь права на запись в /home/codemaster/
        """
    )
    
    parser.add_argument(
        "--mirada-host",
        required=True,
        help="IP адрес или hostname Mirada хоста"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод (debug логи)"
    )
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Создание менеджера развертывания
    deploy_manager = AgentDeployManager(
        mirada_host=args.mirada_host
    )
    
    # Выполнение развертывания
    success = deploy_manager.deploy()
    
    # Возврат кода выхода
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()