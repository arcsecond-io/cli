import click


class State(object):
    def __init__(self, verbose=0, debug=False, open=None, is_using_cli=True):
        self.verbose = verbose
        self.debug = debug
        self.open = open
        self.is_using_cli = is_using_cli


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


def debug_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.debug = value
        return value

    return click.option('-d',
                        '--debug',
                        is_flag=True,
                        expose_value=False,
                        help='Enables or disables debug mode (for arcsecond developers).',
                        callback=callback)(f)


def open_option_constructor(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.open = value
        return value

    return click.option('-o',
                        '--open',
                        is_flag=True,
                        expose_value=False,
                        help="Open the corresponding webpage in the default browser.",
                        callback=callback)(f)


def basic_options(f):
    f = verbose_option_constructor(f)
    f = debug_option_constructor(f)
    return f


def open_options(f):
    f = basic_options(f)
    f = open_option_constructor(f)
    return f


class MethodChoiceParamType(click.ParamType):
    name = 'method'

    def __init__(self, *args):
        super(MethodChoiceParamType, self).__init__()
        self.allowed_methods = args or ['list', 'create', 'read', 'update', 'delete']

    def convert(self, value, param, ctx):
        if value.lower() not in self.allowed_methods:
            msg = '{} is not a valid method. '.format(value)
            msg += 'It must be one of {}.'.format(' '.join(self.allowed_methods))
            self.fail('%s is not a valid method' % value, param, ctx)
        return value.lower()
