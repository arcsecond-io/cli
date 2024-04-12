class ArcsecondError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status

    def __str__(self):
        return self.message
