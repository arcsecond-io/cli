[![Upload Python Package to Pypi](https://github.com/arcsecond-io/cli/actions/workflows/pythonpublish.yml/badge.svg)](https://github.com/arcsecond-io/cli/actions/workflows/pythonpublish.yml) [![Run Tests and Linting](https://github.com/arcsecond-io/cli/actions/workflows/pythonpackage.yml/badge.svg)](https://github.com/arcsecond-io/cli/actions/workflows/pythonpackage.yml) [![Deploy Docs](https://github.com/arcsecond-io/cli/actions/workflows/docsdeploy.yml/badge.svg)](https://github.com/arcsecond-io/cli/actions/workflows/docsdeploy.yml) [![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)

# Arcsecond CLI

The Command-line interface (CLI) for arcsecond.io. It can be used as Python module too.

[Read the docs](https://docs.arcsecond.io/cli)


More documentation is coming.

## Observing Activities

The Arcsecond CLI allows to list, create, read and update so-called observing `activitites`. It is a simple way to publish and let the world know what you are observing.

<h4>The results will be displayed **live** in https://www.arcsecond.io/live</h4>

The usage of th `activities` command is identical to the ones above, with a few more capabilities.

To read the list of the latest 10 activities (this limitation of 10 could evolve in the future):

    $ arcsecond activities 
    $ arcsecond activities read

To read the content of a specific activity, provide the primary key `<pk>` (which is an integer) 

    $ arcsecond activities read <pk> 

To create a new activity, with only title and content (supporting only plain text for now): 

    $ arcsecond activities create --title "your title" --content "the activity content"
    
And finally, to create a full astronomical observing activity:
     
     $ arcsecond activities create --observing_site <uuid> --telescope <uuid> --instrument <uuid> --target <target name>
     
The field of `observing_site`, `telescope` and `instrument` are optionals, and you can provide any (consistent) combination of all.

# Development

To start developing the arcsecond CLI, fork the project, `git clone` it, then, in the arcsecond-cli folder, do (assuming [virtualenv](https://virtualenv.pypa.io/en/stable/) is installed):

```bash
$ cd ~/arcsecond-cli
$ virtualenv --python=pythonX.Y env
$ source env/bin/activate
$ pip install -e .
``` 

The last line ensure you can call the "locally installed" version of the code of that folder. Once done one first time, only the `source env/bin/activate` is needed when you restart a debugging session.
