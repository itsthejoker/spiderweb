from hypothesis import given, strategies as st

from spiderweb.exceptions import (
    SpiderwebException,
    APIError,
    NotFound,
    BadRequest,
    Unauthorized,
    Forbidden,
    ServerError,
    CSRFError,
)


@given(st.text())
def test_spiderweb_exception_str_with_and_without_message(msg):
    # with message
    e1 = SpiderwebException(msg)
    s1 = str(e1)
    if msg:
        assert s1.startswith("SpiderwebException() - ")
        assert msg in s1
    else:
        assert s1 == "SpiderwebException()"
    # without message
    e2 = SpiderwebException()
    assert str(e2) == "SpiderwebException()"


@given(st.integers(), st.one_of(st.none(), st.text(min_size=0)))
def test_apierror_str_contains_code_and_msg(code, maybe_msg):
    e = APIError(code, maybe_msg)
    s = str(e)
    assert str(code) in s
    # msg can be None or string; stringified repr must include it literally
    assert ("None" in s) if maybe_msg is None else (maybe_msg in s)


@given(st.one_of(st.none(), st.text(min_size=0)))
def test_network_subclasses_default_fields(desc):
    # NotFound has fixed values
    nf = NotFound()
    assert nf.code == 404 and nf.msg == "Not Found" and isinstance(nf.desc, str)

    br = BadRequest(desc)
    assert br.code == 400 and br.msg == "Bad Request"
    assert isinstance(br.desc, str)
    if desc is not None and desc != "":
        assert br.desc == desc

    un = Unauthorized(desc)
    assert un.code == 401 and un.msg == "Unauthorized"
    assert isinstance(un.desc, str)

    fb = Forbidden(desc)
    assert fb.code == 403 and fb.msg == "Forbidden"
    assert isinstance(fb.desc, str)

    se = ServerError(desc)
    assert se.code == 500 and se.msg == "Internal Server Error"
    assert isinstance(se.desc, str)

    ce = CSRFError(desc)
    assert ce.code == 403 and ce.msg == "Forbidden"
    assert isinstance(ce.desc, str)
