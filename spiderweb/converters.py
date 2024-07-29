class IntConverter:
    regex = r"\d+"
    name = "int"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


class StrConverter:
    regex = r"[^/]+"
    name = "str"

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return str(value)


class FloatConverter:
    regex = r"\d+\.\d+"
    name = "float"

    def to_python(self, value):
        return float(value)

    def to_url(self, value):
        return str(value)