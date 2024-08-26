import os

from pytest import fixture


@fixture(autouse=True, scope="session")
def db():
    if os.path.exists("spiderweb-tests.db"):
        os.remove("spiderweb-tests.db")
    yield
    if os.path.exists("spiderweb-tests.db"):
        os.remove("spiderweb-tests.db")
