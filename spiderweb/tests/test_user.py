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


def test_user_permissions():
    app, environ, start_response = setup()
    db = app.get_db_session()

    from spiderweb.models.permission import Permission

    user = User(username="perm_user")
    perm1 = Permission(name="View Dashboard", codename="view_dashboard")
    perm2 = Permission(name="Edit Settings", codename="edit_settings")

    user.permissions.extend([perm1, perm2])
    db.add(user)
    db.commit()

    saved_user = db.query(User).filter_by(username="perm_user").first()
    assert len(saved_user.permissions) == 2
    codenames = {p.codename for p in saved_user.permissions}
    assert "view_dashboard" in codenames
    assert "edit_settings" in codenames
    db.close()


def test_add_permission_to_existing_user():
    app, environ, start_response = setup()
    db = app.get_db_session()

    from spiderweb.models.permission import Permission

    user = User(username="existing_add_user")
    db.add(user)
    db.commit()

    perm = Permission(name="Add Perm", codename="add_perm")
    db.add(perm)
    db.commit()

    user.permissions.append(perm)
    db.commit()

    saved_user = db.query(User).filter_by(username="existing_add_user").first()
    assert len(saved_user.permissions) == 1
    assert saved_user.permissions[0].codename == "add_perm"
    db.close()


def test_remove_permission_from_existing_user():
    app, environ, start_response = setup()
    db = app.get_db_session()

    from spiderweb.models.permission import Permission

    user = User(username="existing_remove_user")
    perm = Permission(name="Remove Perm", codename="remove_perm")
    user.permissions.append(perm)
    db.add(user)
    db.commit()

    user.permissions.remove(perm)
    db.commit()

    saved_user = db.query(User).filter_by(username="existing_remove_user").first()
    assert len(saved_user.permissions) == 0
    db.close()
