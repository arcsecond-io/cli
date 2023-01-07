import click


class State(object):

    def __init__(self,
                 is_using_cli=True,
                 verbose=0,
                 api_name='main',
                 api_server='',
                 organisation='',
                 api_key='',
                 upload_key=''):
        self.is_using_cli = is_using_cli
        self.verbose = verbose
        self.api_name = api_name
        self.api_server = api_server
        self.organisation = organisation
        self.api_key = api_key
        self.upload_key = upload_key

    def update(self, **kwargs):
        self.is_using_cli = kwargs.get('is_using_cli', self.is_using_cli)
        self.verbose = kwargs.get('verbose', self.verbose)
        self.api_name = kwargs.get('api_name', self.api_name)
        self.api_server = kwargs.get('api_server', self.api_server)
        self.organisation = kwargs.get('organisation', self.organisation)
        self.api_key = kwargs.get('api_key', self.api_key)
        self.upload_key = kwargs.get('upload_key', self.upload_key)

    @property
    def config_section(self):
        return self.api_name

    def make_new_silent(self):
        return State(verbose=0,
                     api_name=self.api_name,
                     api_server=self.api_server,
                     organisation=self.organisation,
                     is_using_cli=self.is_using_cli,
                     api_key=self.api_key,
                     upload_key=self.upload_key)


# class AliasedGroup(click.Group):
#
#     def get_command(self, ctx, cmd_name):
#         rv = click.Group.get_command(self, ctx, cmd_name)
#         if rv is not None:
#             return rv
#         matches = [x for x in self.list_commands(ctx) if x[0] == cmd_name]
#         if not matches:
#             return None
#         elif len(matches) == 1:
#             return click.Group.get_command(self, ctx, matches[0])
#         ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


def verbose_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.verbose = value
        return value

    return click.option('-v',
                        '--verbose',
                        count=True,
                        expose_value=False,
                        help='Increases verbosity.',
                        callback=callback)(f)


# def test_option_constructor(f):
#     def callback(ctx, param, value):
#         state = ctx.ensure_object(State)
#         state.test = value
#         return value
#
#     return click.option('--test',
#                         is_flag=True,
#                         expose_value=False,
#                         help='Enable test mode (for Arcsecond developers). Implies debug.',
#                         callback=callback)(f)

def api_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.api_name = value
        return value

    return click.option('--api',
                        expose_value=False,
                        help='Choose API name (i.e. API server).',
                        callback=callback)(f)


def organisation_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.organisation = value
        return value

    return click.option('--organisation',
                        help='Perform action as an organisation member. Requires to login as such first.',
                        callback=callback)(f)


# def open_option_constructor(f):
#     def callback(ctx, param, value):
#         state = ctx.ensure_object(State)
#         state.open = value
#         return value
#
#     return click.option('-o',
#                         '--open',
#                         is_flag=True,
#                         expose_value=False,
#                         help="Open the corresponding webpage in the default browser.",
#                         callback=callback)(f)


def basic_options(f):
    f = verbose_option_constructor(f)
    f = api_option_constructor(f)
    return f


def organisation_options(f):
    f = basic_options(f)
    f = api_option_constructor(f)
    f = organisation_option_constructor(f)
    return f


# def open_options(f):
#     f = basic_options(f)
#     f = open_option_constructor(f)
#     return f


class MethodChoiceParamType(click.ParamType):
    name = 'method'

    def __init__(self, *args):
        super().__init__()
        self.allowed_methods = args or ['list', 'create', 'read', 'update', 'delete']

    def convert(self, value, param, ctx):
        if value.lower() not in self.allowed_methods:
            msg = '{} is not a valid method. '.format(value)
            msg += 'It must be one of {}.'.format(' '.join(self.allowed_methods))
            self.fail('%s is not a valid method' % value, param, ctx)
        return value.lower()
