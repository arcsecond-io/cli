import click


class ArcsecondError(click.ClickException):
    """Anything the CLI has to refuse or could not do.

    A ClickException so that, raised from a command, it is printed as one
    `Error: ...` and the process exits 1 — not a traceback. Raised from the
    Python API it is an ordinary exception with a message and a status.
    """

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status

    def __str__(self):
        return self.message
