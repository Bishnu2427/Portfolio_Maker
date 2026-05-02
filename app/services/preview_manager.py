import os
import sys
import subprocess
import socket
import time
import psutil
from app.models.port_registry import PortRegistry


def _wait_for_server(port: int, timeout: int = 20) -> bool:
    """Poll until the preview Flask server accepts TCP connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.4)
    return False


class PreviewManager:
    # Maps portfolio_id → (subprocess.Popen, log_file_handle)
    _procs: dict = {}

    def start(self, portfolio_dir: str, port: int, portfolio_id: str) -> int:
        app_path = os.path.join(portfolio_dir, 'app.py')
        env = {**os.environ, 'PORTFOLIO_PORT': str(port)}

        log_path = os.path.join(portfolio_dir, 'preview.log')
        log_fh = open(log_path, 'w', buffering=1)

        proc = subprocess.Popen(
            [sys.executable, '-u', app_path],
            cwd=portfolio_dir,
            stdout=log_fh,
            stderr=log_fh,
            env=env,
        )
        self.__class__._procs[portfolio_id] = (proc, log_fh)

        # Register in MongoDB with real PID — single source of truth
        PortRegistry.register(portfolio_id, port, proc.pid)
        print(f'[PreviewManager] Started portfolio {portfolio_id[:8]} on port {port} (PID {proc.pid})')
        PortRegistry.print_log()
        return proc.pid

    def wait_ready(self, port: int) -> bool:
        """Block until the server is accepting connections (max 20 s)."""
        return _wait_for_server(port)

    def get_log(self, portfolio_id: str) -> str:
        item = self.__class__._procs.get(portfolio_id)
        if not item:
            return ''
        _, log_fh = item
        try:
            log_fh.flush()
            with open(log_fh.name, 'r') as f:
                return f.read()
        except Exception:
            return ''

    def stop(self, portfolio_id: str):
        item = self.__class__._procs.pop(portfolio_id, None)
        if item:
            proc, log_fh = item
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
            except psutil.NoSuchProcess:
                pass
            try:
                log_fh.close()
            except Exception:
                pass
        PortRegistry.deregister(portfolio_id)
        print(f'[PreviewManager] Stopped portfolio {portfolio_id[:8]}')

    def is_running(self, portfolio_id: str) -> bool:
        item = self.__class__._procs.get(portfolio_id)
        if not item:
            return False
        proc, _ = item
        return proc.poll() is None
