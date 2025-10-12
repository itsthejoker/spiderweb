from hypothesis import given, strategies as st, settings, HealthCheck

from spiderweb.db import create_sqlite_engine


@given(
    sub1=st.text(
        min_size=1,
        max_size=8,
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    ),
    sub2=st.text(
        min_size=1,
        max_size=8,
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    ),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_create_sqlite_engine_creates_parent_directories(tmp_path, sub1, sub2):
    # Construct nested path that does not yet exist
    db_path = tmp_path / sub1 / sub2 / "test.sqlite"
    assert not db_path.parent.exists()

    engine = create_sqlite_engine(db_path)
    try:
        # Parent dirs should be created and engine should connect to sqlite
        assert db_path.parent.exists()
        conn = engine.connect()
        conn.close()
    finally:
        engine.dispose()  # ensure resources are freed even under coverage
