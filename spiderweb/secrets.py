from cryptography.fernet import Fernet

from spiderweb.constants import DEFAULT_ENCODING


class FernetMiddleware:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    fernet: Fernet
    secret_key: str

    def init_fernet(self):
        self.fernet = Fernet(self.secret_key)

    def generate_key(self):
        return Fernet.generate_key()

    def encrypt(self, data: str):
        return self.fernet.encrypt(bytes(data, DEFAULT_ENCODING))

    def decrypt(self, data: str):
        if isinstance(data, bytes):
            return self.fernet.decrypt(data).decode(DEFAULT_ENCODING)
        return self.fernet.decrypt(bytes(data, DEFAULT_ENCODING)).decode(
            DEFAULT_ENCODING
        )
