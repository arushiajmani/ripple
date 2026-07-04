# Intentional cycle: models → utils → models (for CycleDetector / pipeline demos).
from myapp.utils import hash_password


class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def fingerprint(self) -> str:
        return hash_password(self.name)
