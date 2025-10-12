from hypothesis import given, strategies as st
import pytest

from spiderweb.server_checks import ServerCheck


def test_server_check_noop():
    class Srv: ...

    sc = ServerCheck(Srv())
    # Should not raise
    sc.check()


class PassingCheck(ServerCheck):
    def __init__(self, server, record):
        super().__init__(server)
        self.record = record

    def check(self):
        # Indicate we ran without error
        self.record.append("ok")


class FailingCheck(ServerCheck):
    def __init__(self, server, exc: Exception):
        super().__init__(server)
        self.exc = exc

    def check(self):
        raise self.exc


@given(name=st.text())
def test_server_check_passes_and_records(name):
    class Srv:
        def __init__(self, name):
            self.name = name

    record = []
    sc = PassingCheck(Srv(name), record)
    # Should not raise
    sc.check()
    assert record == ["ok"]
    # Ensure the base class kept our server reference
    assert sc.server.name == name


@given(
    exc_cls=st.sampled_from([ValueError, RuntimeError, KeyError]),
    msg=st.text(),
)
def test_server_check_fails_and_raises(exc_cls, msg):
    class Srv:
        pass

    sc = FailingCheck(Srv(), exc_cls(msg))
    with pytest.raises(exc_cls) as ei:
        sc.check()
    # args[0] should preserve the original message (KeyError str adds quotes, so check args)
    assert ei.value.args and ei.value.args[0] == msg
