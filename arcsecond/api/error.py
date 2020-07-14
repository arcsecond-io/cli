class ArcsecondError(Exception):
    pass


class ArcsecondInputValueError(ArcsecondError):
    def __init__(self, msg):
        super().__init__(msg)


class ArcsecondNotLoggedInError(ArcsecondError):
    def __init__(self):
        msg = "Not logged in. You must login (or register) first."
        super().__init__(msg)


class ArcsecondInvalidEndpointError(ArcsecondError):
    def __init__(self, endpoint, endpoints):
        msg = "Unknown endpoint {}. ".format(endpoint)
        msg += "It must be one of: {}".format(', '.join(endpoints))
        super().__init__(msg)


class ArcsecondConnectionError(ArcsecondError):
    def __init__(self, url):
        msg = "Unable to connect to API server {}.\n".format(url)
        msg += "Suggestion: Test whether it's reachable, by typing for instance: 'curl -Is {} | head -n 1'".format(url)
        super().__init__(msg)


class ArcsecondRequestTimeoutError(ArcsecondError):
    def __init__(self, url):
        msg = "Requests to {} timeout.\n".format(url)
        super().__init__(msg)


class ArcsecondTooManyPrefixesError(ArcsecondError):
    def __init__(self, prefixes):
        msg = "Too many endpoint prefixes: {}.\n".format(', '.join(prefixes))
        msg += "Only one can be used at a time."
        super().__init__(msg)
