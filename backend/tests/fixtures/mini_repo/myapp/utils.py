import json

from myapp.models import User


def hash_password(password: str) -> str:
    return json.dumps({"password": password})


def make_user(name: str) -> User:
    return User(name)

class Helper:
    def __init__(self, name: str) -> None:
        self.name = name

    def get_name(self) -> str:
        return self.name