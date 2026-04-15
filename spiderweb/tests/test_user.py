from datetime import datetime

from spiderweb.models.user import User
from spiderweb.tests.helpers import setup


def test_user_creation():
    app, environ, start_response = setup()
    db = app.get_db_session()
    user = User(
        username="testuser",
        first_name="Test",
        last_name="User",
        email="test@example.com",
    )
    user.set_password("mypassword")
    db.add(user)
    db.commit()

    saved_user = db.query(User).filter_by(username="testuser").first()
    assert saved_user is not None
    assert saved_user.id is not None
    assert saved_user.username == "testuser"
    assert saved_user.first_name == "Test"
    assert saved_user.last_name == "User"
    assert saved_user.email == "test@example.com"
    assert saved_user.is_staff is False
    assert saved_user.is_superuser is False
    assert saved_user.is_active is True
    assert isinstance(saved_user.date_joined, datetime)
    db.close()


def test_user_names():
    user = User(username="jsmith", first_name="John", last_name="Smith")
    assert str(user) == "jsmith"
    assert user.get_username() == "jsmith"
    assert user.get_full_name() == "John Smith"
    assert user.get_short_name() == "John"

    user_no_last = User(username="jdoe", first_name="John")
    assert user_no_last.get_full_name() == "John"


def test_password_hashing():
    user = User(username="test")
    assert user.has_usable_password() is False

    user.set_password("mysecret")
    assert user.has_usable_password() is True
    assert user.check_password("mysecret") is True
    assert user.check_password("wrongsecret") is False

    # Check empty string is rejected
    assert user.check_password("") is False
    assert user.check_password(None) is False

    # Test unusable passwords
    user.set_unusable_password()
    assert user.has_usable_password() is False
    assert user.check_password("mysecret") is False

    # Test setting empty password
    user.set_password("")
    assert user.has_usable_password() is False

    user.set_password(None)
    assert user.has_usable_password() is False


def test_invalid_hash():
    user = User(username="test")
    # Missing fields
    user.password = "pbkdf2_sha256$600000$salt"
    assert user.check_password("test") is False

    # Invalid iterations
    user.password = "pbkdf2_sha256$invalid$salt$hash"
    assert user.check_password("test") is False

    # Invalid algo
    user.password = "md5$1000$salt$hash"
    assert user.check_password("test") is False
