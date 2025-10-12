from hypothesis import given, strategies as st
from cryptography.fernet import Fernet

from spiderweb.secrets import FernetMixin


class DummySecrets(FernetMixin):
    def __init__(self, key: bytes):
        self.secret_key = key
        self.init_fernet()


@given(st.text())
def test_encrypt_decrypt_round_trip_for_str(data):
    ds = DummySecrets(Fernet.generate_key())
    token = ds.encrypt(data)
    assert isinstance(token, bytes)
    assert ds.decrypt(token) == data


@given(st.text())
def test_decrypt_accepts_str_and_bytes_inputs(data):
    ds = DummySecrets(Fernet.generate_key())
    token = ds.encrypt(data)
    # bytes input
    assert ds.decrypt(token) == data
    # str input (base64 token decoded in method)
    token_str = token.decode()
    assert ds.decrypt(token_str) == data
