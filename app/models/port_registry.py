from datetime import datetime
from app.extensions import mongo


class PortRegistry:
    COLLECTION = 'port_registry'

    @staticmethod
    def get_next_available(start_port, end_port):
        used_ports = {
            doc['port']
            for doc in mongo.db[PortRegistry.COLLECTION].find({'active': True})
        }
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                return port
        return None

    @staticmethod
    def register(portfolio_id, port, pid=None):
        mongo.db[PortRegistry.COLLECTION].update_one(
            {'portfolio_id': str(portfolio_id)},
            {
                '$set': {
                    'portfolio_id': str(portfolio_id),
                    'port': port,
                    'pid': pid,
                    'active': True,
                    'created_at': datetime.utcnow(),
                }
            },
            upsert=True,
        )

    @staticmethod
    def deregister(portfolio_id):
        mongo.db[PortRegistry.COLLECTION].update_one(
            {'portfolio_id': str(portfolio_id)},
            {'$set': {'active': False, 'stopped_at': datetime.utcnow()}},
        )

    @staticmethod
    def get_by_portfolio(portfolio_id):
        return mongo.db[PortRegistry.COLLECTION].find_one(
            {'portfolio_id': str(portfolio_id), 'active': True}
        )

    @staticmethod
    def get_all_active():
        return list(mongo.db[PortRegistry.COLLECTION].find({'active': True}))

    @staticmethod
    def print_log():
        from app.config import Config
        active = PortRegistry.get_all_active()
        print("\n" + "="*40)
        print(f"  PORT REGISTRY LOG")
        print(f"  Main App   : port {Config.MAIN_APP_PORT}")
        for entry in active:
            pid_info = f"PID {entry.get('pid', 'N/A')}"
            print(f"  Portfolio  : port {entry['port']}  ({pid_info})")
        print("="*40 + "\n")
