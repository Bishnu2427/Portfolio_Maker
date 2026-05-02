import socket
from app.models.port_registry import PortRegistry
from app.config import Config


class PortManager:
    def __init__(self):
        self.start = Config.PORT_START
        self.end = Config.PORT_END

    def _is_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('127.0.0.1', port)) != 0

    def allocate_port(self, portfolio_id: str) -> int:
        port = PortRegistry.get_next_available(self.start, self.end)
        if port is None:
            raise RuntimeError('No free ports available in range.')
        while not self._is_free(port):
            port += 1
            if port > self.end:
                raise RuntimeError('No free ports available.')
        # Registration (with PID) is done by PreviewManager after the process starts
        print(f'[PortManager] Reserved port {port} for portfolio {portfolio_id[:8]}')
        return port

    def release_port(self, portfolio_id: str):
        PortRegistry.deregister(portfolio_id)
        print(f'[PortManager] Released port for portfolio {portfolio_id[:8]}')
