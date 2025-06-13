import random
import string

from multipart import MultipartPart


class MediaFile:
    # This class acts as a sort of container for uploaded files.
    # Rather than trying to subclass the MultipartPart class and deal with
    # the complexities of multipart parsing, we just use this class to
    # add the save functionality for the media folder. Also makes the most
    # common attributes available directly on the instance.
    def __init__(self, server, multipart_part: MultipartPart):
        self._file: MultipartPart = multipart_part
        self.filename: str = self._file.filename
        self.content_type: str = self._file.content_type
        self.server = server
        #: Part size in bytes.
        self.size = self._file.size
        #: Part name.
        self.name = self._file.name
        #: Charset as defined in the part header, or the parser default charset.
        self.charset = self._file.charset
        #: All part headers as a list of (name, value) pairs.
        self.headerlist = self._file.headerlist

        self.memfile_limit = self._file.memfile_limit
        self.buffer_size = self._file.buffer_size

    def get_random_suffix(self) -> str:
        """Generate a random 6 character suffix."""
        return "".join(random.choices(string.ascii_letters, k=6))

    def save(self):
        file_path = self.server.BASE_DIR / self.server.media_dir / self._file.filename
        if file_path.exists():
            # If the file already exists, append a random suffix to the filename
            suffix = self.get_random_suffix()
            file_path = file_path.with_name(
                f"{file_path.stem}_[{suffix}]{file_path.suffix}"
            )
        self._file.save_as(file_path)
        return file_path

    def read(self):
        return self._file.file.read()

    def seek(self, offset: int, whence: int = 0):
        return self._file.file.seek(offset, whence)
