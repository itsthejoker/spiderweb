import string
from io import BytesIO
from pathlib import Path

from hypothesis import given, strategies as st, settings, HealthCheck

from spiderweb.files import MediaFile


class FakeMultipartPart:
    def __init__(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        name: str,
        charset: str | None,
        headerlist: list[tuple[str, str]],
        memfile_limit: int,
        buffer_size: int,
    ):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(data)
        self.size = len(data)
        self.name = name
        self.charset = charset
        self.headerlist = headerlist
        self.memfile_limit = memfile_limit
        self.buffer_size = buffer_size

    def save_as(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.file.getvalue())


class FakeServer:
    def __init__(self, base_dir: Path, media_dir: Path | str):
        self.BASE_DIR = base_dir
        self.media_dir = media_dir


# Strategies
safe_stem = st.text(
    alphabet=string.ascii_letters + string.digits + "_-",
    min_size=1,
    max_size=12,
)
safe_ext = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=4).map(
    lambda s: "." + s
)
filenames = st.builds(lambda stem, ext: stem + ext, safe_stem, safe_ext)
content_types = st.sampled_from(["application/octet-stream", "text/plain", "image/png"])
part_names = st.text(
    alphabet=string.ascii_letters + string.digits + "_-", min_size=1, max_size=20
)
charsets = st.one_of(st.none(), st.sampled_from(["utf-8", "latin-1"]))
header_pairs = st.tuples(
    st.text(alphabet=string.ascii_letters + "-", min_size=1, max_size=12),
    st.text(alphabet=string.printable, min_size=0, max_size=20),
)
headerlists = st.lists(header_pairs, max_size=3)
mem_limits = st.integers(min_value=1024, max_value=1024 * 1024)
buf_sizes = st.integers(min_value=1, max_value=64 * 1024)


@given(
    filename=filenames,
    content_type=content_types,
    data=st.binary(max_size=512),
    name=part_names,
    charset=charsets,
    headerlist=headerlists,
    memfile_limit=mem_limits,
    buffer_size=buf_sizes,
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_mediafile_attribute_passthrough_and_read_seek(
    tmp_path,
    filename,
    content_type,
    data,
    name,
    charset,
    headerlist,
    memfile_limit,
    buffer_size,
):
    media_dir = tmp_path / "media"
    media_dir.mkdir(exist_ok=True)
    server = FakeServer(tmp_path, media_dir.relative_to(tmp_path))

    part = FakeMultipartPart(
        filename=filename,
        content_type=content_type,
        data=data,
        name=name,
        charset=charset,
        headerlist=headerlist,
        memfile_limit=memfile_limit,
        buffer_size=buffer_size,
    )

    mf = MediaFile(server, part)

    # Attribute passthrough
    assert mf.filename == filename
    assert mf.content_type == content_type
    assert mf.size == len(data)
    assert mf.name == name
    assert mf.charset == charset
    assert mf.headerlist == headerlist
    assert mf.memfile_limit == memfile_limit
    assert mf.buffer_size == buffer_size

    # read/seek delegate to underlying file
    assert mf.read() == data
    assert mf.seek(0) == 0
    assert mf.read() == data

    # Save without existing collision (ensure clean path per example)
    dest = tmp_path / server.media_dir / filename
    if dest.exists():
        dest.unlink()
    saved_path = mf.save()
    assert saved_path == dest
    assert saved_path.exists()
    assert saved_path.read_bytes() == data


@given(
    filename=filenames,
    data=st.binary(min_size=1, max_size=256),
    suffix=st.text(alphabet=string.ascii_letters, min_size=6, max_size=6),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_mediafile_save_adds_random_suffix_on_collision(
    tmp_path, monkeypatch, filename, data, suffix
):
    media_dir = tmp_path / "uploads"
    media_dir.mkdir(exist_ok=True)
    server = FakeServer(tmp_path, media_dir.relative_to(tmp_path))

    # Pre-create a file to force collision
    existing_path = tmp_path / server.media_dir / filename
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_bytes(b"existing")

    part = FakeMultipartPart(
        filename=filename,
        content_type="application/octet-stream",
        data=data,
        name="file",
        charset="utf-8",
        headerlist=[],
        memfile_limit=1024,
        buffer_size=8192,
    )

    mf = MediaFile(server, part)

    # Force deterministic suffix using randomized letters
    monkeypatch.setattr(MediaFile, "get_random_suffix", lambda self: suffix)

    saved_path = mf.save()

    # Expected name: <stem>_[<suffix>]<ext>
    original = Path(filename)
    expected_name = f"{original.stem}_[{suffix}]{original.suffix}"
    assert saved_path.name == expected_name
    assert saved_path.parent == existing_path.parent

    # Ensure new content written, old file remains
    assert saved_path.read_bytes() == data
    assert existing_path.read_bytes() == b"existing"


def test_get_random_suffix_properties():
    # Call multiple times to increase confidence
    mf = object.__new__(MediaFile)  # bypass __init__ to access method
    # Bind a minimal server/file to avoid attribute access (not needed for this test)
    # Just verify output characteristics
    outputs = {MediaFile.get_random_suffix(mf) for _ in range(10)}
    assert all(len(s) == 6 for s in outputs)
    assert all(set(s) <= set(string.ascii_letters) for s in outputs)
