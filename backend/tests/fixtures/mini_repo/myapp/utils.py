import json

from myapp.models import User


def hash_password(password: str) -> str:
    return json.dumps({"password": password})


def make_user(name: str) -> User:
    return User(name)
