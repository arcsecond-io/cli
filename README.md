[![Deploy Docs](https://github.com/arcsecond-io/cli/actions/workflows/docsdeploy.yml/badge.svg)](https://github.com/arcsecond-io/cli/actions/workflows/docsdeploy.yml) [![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)

# Arcsecond CLI

The Command-line interface (CLI) for Arcsecond. It can be used as Python 
module too. The CLI makes it easy to login/register and access Arcsecond resources,
public and private ones.

[Read the docs](https://docs.arcsecond.io/cli)

# Development

To start developing the arcsecond CLI, fork the project, `git clone` it, 
then, in the arcsecond-cli folder, do 
(assuming [virtualenv](https://virtualenv.pypa.io/en/stable/) is installed):

```bash
$ cd ~/arcsecond-cli
$ virtualenv --python=pythonX.Y env
$ source env/bin/activate
$ pip install -e .
``` 

The last line ensure you can call the "locally installed" version of the 
code of that folder. Once done one first time, only the `source 
env/bin/activate` is needed when you restart a debugging session.
