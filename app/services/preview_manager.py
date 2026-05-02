import os
import sys
import subprocess
import psutil
from app.models.port_registry import PortRegistry


class PreviewManager:
    _procs: dict = {}

    def start(self, portfolio_dir: str, port: int, portfolio_id: str) -> int:
        app_path = os.path.join(portfolio_dir, 'app.py')
        # Pass port via env var — no local port.txt file written
        env = {**os.environ, 'PORTFOLIO_PORT': str(port)}
        proc = subprocess.Popen(
            [sys.executable, app_path],
            cwd=portfolio_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self.__class__._procs[portfolio_id] = proc
        # Register now that PID is known — single source of truth in MongoDB
        PortRegistry.register(portfolio_id, port, proc.pid)
        print(f'[PreviewManager] Started portfolio {portfolio_id[:8]} on port {port} (PID {proc.pid})')
        PortRegistry.print_log()
        return proc.pid

    def stop(self, portfolio_id: str):
        proc = self.__class__._procs.pop(portfolio_id, None)
        if proc:
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
            except psutil.NoSuchProcess:
                pass
        PortRegistry.deregister(portfolio_id)
        print(f'[PreviewManager] Stopped portfolio {portfolio_id[:8]}')

    def is_running(self, portfolio_id: str) -> bool:
        proc = self.__class__._procs.get(portfolio_id)
        return proc is not None and proc.poll() is None
