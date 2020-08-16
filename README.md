[![Build Status](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Factions-badge.atrox.dev%2Farcsecond-io%2Fcli%2Fbadge&style=flat)](https://actions-badge.atrox.dev/arcsecond-io/cli/goto) [![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)

# Arcsecond CLI

The Command-line interface (CLI) for arcsecond.io. It can be used as Python module too.


# Installation

Simply run:

    $ pip install arcsecond

Then the Help is accessible like any other command line:

    $ arcsecond --help

or 

    $ arcsecond <command> --help
    
    
# Get Started 
    
**You must login first before accessing APIs.** This is for both making easy to access private APIs, as well as server
logging, to better understand the usage that is made of our APIs. 

    $ arcsecond login 
    
To skip prompts:

    $ arcsecond login --username <username> --password <password>

Login again will overwrite the current API key with the new one (assuming login is a success).

You can also register directly from there:

    $ arcsecond register 

Your private API key will be stored in the config file in `~/.arcsecond.ini`. Then, you can access public and private APIs. 

Then, you can access your own full profile:

    $ arcsecond me

See below for all commands.

# Usage

Philosophy: the Arcsecond CLI is using the same principle as `git`: it has a global
command `arcsecond` followed by subcommands. And **subcommands have the name of API endpoints.**

For instance, to obtain the information about an object, and likewise, an exoplanet:

    $ arcsecond objects "HD 5980"
    $ arcsecond exoplanets "51 Peg b"
         
For objects, and exoplanets, you can open the webpage in the default browser:     

     $ arcsecond objects "HD 5980" --open
     $ arcsecond exoplanets "51 Peg b" --open

Or open the API webpage in the default browser for that object:     

     $ arcsecond o "HD 5980" --open api
     $ arcsecond exoplanets "51 Peg b" --open api
    
For other things, such as private observing runs and night logs, likewise:

    $ arcsecond observingruns <uuid>
    $ arcsecond nightlogs <uuid>    

Using this as a Python module goes as follow

    >>> from arcsecond import ArcsecondAPI
    >>> ArcsecondAPI.login(<username>, <password>)
    >>> ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBJECTS).read('HD 5980')

## Available Endpoints

The available **read-only** API endpoints (and thus, subcommands) available so far are: 
* `objects`, `exoplanets`, and `findingcharts` (public)
* `observingsites`, `telescopes` and `instruments` (public)
* `profiles` (public)
* `satellites` (public)
* `observingruns` and `nightlogs` (private)
* `me` (personal profile, private)

Observing Runs and Night Logs will be writable in a near future. As for Observing Sites, Telescopes
and Instruments, this is under study.

The available **read-write** API endpoints available so far are: 
* `activities` (public)
* `datasets` and `datafiles` (private)

Read-write APIs use the 4 standard CRUD methods: `create`, `read`, `update`, `delete` (while, read-only APIs
have only the `read` method, implicitly).

See below for details.

## Datasets and Data files

**You can entirely manage your datasets and Data/FITS files (including upload) from this CLI / Python module.**

To list your datasets (the two methods are identical, the second simply having its action name explicitly written):

    $ arcsecond datasets
    $ arcsecond datasets read
    
To create a dataset:

    $ arcsecond datasets create --name "this is a new dataset"

To delete a dataset (**warning: this will also delete the associated data/FITS files!**):

    $ arcsecond datasets delete <dataset uuid>
    
Data files are necessarily associated with a dataset. Hence a dataset UUID must be provided.
To upload a data file:

    $ arcsecond datafiles <dataset uuid> create --file <path to a local data file>
    
To delete a data file, one use its "id/pk" (pk = Primary Key == ID):

    $ arcsecond datafiles <dataset uuid> delete <Data file pk>
    
As a Python module:

    >>> from arcsecond import ArcsecondAPI
    >>> api = ArcsecondAPI.datafiles(dataset='<dataset_uuid>')
    >>> api.create(file='<file path>')    

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