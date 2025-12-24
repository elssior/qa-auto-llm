"""
Упрощённый менеджер SSH-туннелей для проброса портов.
Только базовые функции: создать/закрыть туннель, проверить порт.
"""
import subprocess
import socket
import logging
import platform
import os

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"
IS_UNIX = not IS_WINDOWS

class SSHTunnelManager:
    def __init__(self, mirada_host: str, username: str = "codemaster"):
        self.mirada_host = mirada_host
        self.username = username
        self.tunnels = {}

    def _test_agent_health(self, local_port: int) -> bool:
        """Проверяет доступность агента по локальному порту."""
        return self._is_port_available(local_port)

    def _is_port_available(self, port: int) -> bool:
        """True если порт занят (туннель работает)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False

    def _get_ssh_executable(self):
        """Возвращает путь к SSH клиенту."""
        candidates = [
            'ssh',
            'C:\\Windows\\System32\\OpenSSH\\ssh.exe',
            'C:\\Program Files\\Git\\usr\\bin\\ssh.exe',
            'C:\\Program Files (x86)\\Git\\usr\\bin\\ssh.exe',
            '/usr/bin/ssh',
            '/usr/local/bin/ssh',
        ]
        for path in candidates:
            try:
                result = subprocess.run([path, '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                if result.returncode == 0 or b'OpenSSH' in result.stderr:
                    return path
            except Exception:
                continue
        return None

    def create_tunnel(self, service_name: str, local_port: int, remote_port: int, remote_host: str = "127.0.0.1") -> bool:
        """Создаёт SSH-туннель."""
        tunnel_key = f"{service_name}_{local_port}"
        if tunnel_key in self.tunnels:
            proc = self.tunnels[tunnel_key]
            if proc.poll() is None:
                logger.info(f"Tunnel {tunnel_key} already running")
                return True
            else:
                del self.tunnels[tunnel_key]

        ssh_exe = self._get_ssh_executable()
        if not ssh_exe:
            logger.error("SSH client not found.")
            return False

        ssh_cmd = [
            ssh_exe,
            "-N",
            "-L", f"127.0.0.1:{local_port}:{remote_host}:{remote_port}",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            f"{self.username}@{self.mirada_host}"
        ]
        if IS_WINDOWS:
            ssh_cmd += ["-o", "UserKnownHostsFile=NUL"]
        else:
            ssh_cmd += ["-o", "UserKnownHostsFile=/dev/null"]

        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'stdin': subprocess.PIPE,
        }
        if IS_UNIX and hasattr(os, 'setsid'):
            popen_kwargs['preexec_fn'] = os.setsid
        elif IS_WINDOWS:
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            proc = subprocess.Popen(ssh_cmd, **popen_kwargs)
            for _ in range(5):
                if proc.poll() is None and self._is_port_available(local_port):
                    self.tunnels[tunnel_key] = proc
                    logger.info(f"Tunnel {tunnel_key} created (PID: {proc.pid})")
                    return True
                else:
                    logger.info(f"Waiting for tunnel {tunnel_key}...")
                    import time; time.sleep(2)
            proc.terminate()
            logger.error(f"Tunnel {tunnel_key} failed to start.")
            return False
        except Exception as e:
            logger.error(f"Error creating tunnel: {e}")
            return False

    def close_tunnel(self, service_name: str, local_port: int) -> bool:
        """Закрывает SSH-туннель."""
        tunnel_key = f"{service_name}_{local_port}"
        if tunnel_key not in self.tunnels:
            logger.info(f"Tunnel {tunnel_key} not found.")
            return True
        proc = self.tunnels[tunnel_key]
        try:
            if proc.poll() is None:
                proc.terminate()
            del self.tunnels[tunnel_key]
            logger.info(f"Tunnel {tunnel_key} closed.")
            return True
        except Exception as e:
            logger.error(f"Error closing tunnel: {e}")
            return False
