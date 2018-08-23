class ArcsecondError(Exception):
    pass


class ArcsecondInvalidEndpointError(ArcsecondError):
    def __init__(self, endpoint, endpoints):
        msg = "Unknown endpoint {}. ".format(endpoint)
        msg += "It must be one of: {}".format(', '.join(endpoints))
        super().__init__()
