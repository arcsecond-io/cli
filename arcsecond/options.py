import click


class State(object):
    """Object to collect the state of CLI commands.
    Its properties will be transferred to the ArcsecondConfig object which will manage
    the persistence of the various parameters.
    """

    def __init__(self, **kwargs):
        self.verbose = kwargs.get("verbose", 0)
        self.api_name = kwargs.get("api_name", "cloud")

    def update(self, **kwargs):
        self.verbose = kwargs.get("verbose", self.verbose)
        self.api_name = kwargs.get("api_name", self.api_name)

    def make_new_silent(self):
        return State(verbose=0, api_name=self.api_name)


def verbose_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.verbose = value
        return value

    return click.option(
        "-v",
        "--verbose",
        count=True,
        expose_value=False,
        help="Increases verbosity.",
        callback=callback,
    )(f)


def api_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.api_name = value
        return value

    return click.option(
        "--api",
        expose_value=False,
        help="Choose API name (i.e. API server).",
        callback=callback,
    )(f)


def basic_options(f):
    f = verbose_option_constructor(f)
    f = api_option_constructor(f)
    return f
