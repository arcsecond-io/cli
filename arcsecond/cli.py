import json
import pprint
import sys

import click
import requests
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

pp = pprint.PrettyPrinter(indent=4, depth=5)


@click.group()
def main():
    pass


@main.command()
@click.argument('name', required=True)
def objects(name):
    r = requests.get('https://api.arcsecond.io/objects/' + name)
    if r.status_code == 200:
        json_str = json.dumps(r.json(), indent=4, sort_keys=True)
        print(highlight(json_str, JsonLexer(), TerminalFormatter()))


if __name__ == '__main__':
    main(sys.argv[1:])
