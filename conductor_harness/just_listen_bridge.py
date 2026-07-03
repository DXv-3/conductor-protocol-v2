from datetime import datetime, timezone
from pathlib import Path

class JustListenBridge:
    def __init__(self, persistence_dir: str):
        self.dir = Path(persistence_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def start_listening(self):
        pass

    def collect_observation(self, observation: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        with open(self.dir / "observations.log", "a") as f:
            f.write(f"{timestamp} {observation}\n")

    def recent_observations(self, limit=10):
        try:
            lines = (self.dir / "observations.log").read_text().splitlines()
            return lines[-limit:]
        except FileNotFoundError:
            return []
