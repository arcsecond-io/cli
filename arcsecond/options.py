import click


class State(object):
    def __init__(self):
        self.verbose = 0
        self.debug = False
        self.open = None


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x[0] == cmd_name]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


def verbose_option(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.verbose = value
        return value

    return click.option('-v', '--verbose',
                        count=True,
                        expose_value=False,
                        help='Increases verbosity.',
                        callback=callback)(f)


def debug_option(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.debug = value
        return value

    return click.option('--debug',
                        is_flag=True,
                        expose_value=False,
                        help='Enables or disables debug mode.',
                        callback=callback)(f)


def open_option(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.open = value
        return value

    return click.option('-o', '--open',
                        is_flag=True,
                        expose_value=False,
                        help="Open the corresponding webpage in the default browser.",
                        callback=callback)(f)


def common_options(f):
    f = verbose_option(f)
    f = debug_option(f)
    f = open_option(f)
    return f