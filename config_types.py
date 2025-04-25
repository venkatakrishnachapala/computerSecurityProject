from argparse import Namespace
from enum import Enum


class TRAVERSAL(str, Enum):
    TABLE  = 'table',
    COLUMN = 'column'

class BREAKAGE(str, Enum):
    LENGTH = 'length',
    URL    = 'url'

class SCANNER(str, Enum):
    NONE       = 'none',
    BLACKWIDOW = 'blackwidow'


class AppConfig(Namespace):
    def __init__(self, app: str, blacklist: set[str], allowlist: set[str] | None,
                 urls_seed: list[str], cookies: str, login: str,
                 credentials: str, args) -> None:
        self.app = app
        self.blacklist = blacklist
        self.allowlist = allowlist
        self.urls_seed = urls_seed
        self.urls = []
        self.cookies = cookies
        self.login = login
        self.credentials = credentials
        for arg in vars(args):
            setattr(self, arg, getattr(args, arg))

    def __str__(self):
        return self.app
