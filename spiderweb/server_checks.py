class ServerCheck:
    """
    Single server check base class.

    During startup, each middleware can request checks to be run against the
    current state of the server. These are usually used to verify that things
    are configured correctly, but can also be used for database setup or other
    similar things.

    To fail a check, raise any error that makes sense to raise. This will halt
    startup so the error can be fixed.
    """

    def __init__(self, server):
        self.server = server

    def check(self):
        pass
