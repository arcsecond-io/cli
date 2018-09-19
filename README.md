[![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)

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
    
**You must login first before accessing APIs.** This is for logging purpose and better understanding of the usage that is made of our APIs. 

    $ arcsecond login 
    
To skip prompts:

    $ arcsecond login --username <username> --password <password>

You can also register directly from there:

    $ arcsecond register 

Your private API key will be stored in the config file in `~/.arcsecond.ini`. Then, you can access public and private APIs. 

# Usage

Philosophy: the Arcsecond CLI is using the same principle as `git`: it has a global
command `arcsecond` followed by subcommands.

## Public APIs

For instance, to obtain the information about an object, and likewise, an exoplanet:

    $ arcsecond objects "HD 5980"
    $ arcsecond exoplanets "51 Peg b"
         
For objects, and exoplanets, you can open the webpage in the default browser:     

     $ arcsecond objects "HD 5980" --open
     $ arcsecond exoplanets "51 Peg b" --open

Or open the API webpage in the default browser for that object:     

     $ arcsecond o "HD 5980" --open api
     $ arcsecond exoplanets "51 Peg b" --open api

## Private APIs

You can access your own fill profile:

    $ arcsecond me
    
For other things, likewise:

    $ arcsecond observingruns <uuid>
    $ arcsecond nightlogs <uuid>    

## Available Endpoints

The available **read-only** public API endpoints (and thus, subcommands) available so far are: 
* `objects`, `exoplanets`, and `findingcharts`
* `observingsites`, `telescopes` and `instruments`
* `profiles`

Se below for `activities` !

The available **read-only** private API endpoints (and thus, subcommands) available so far are: 
* `me` (personnal profile)
* `observingruns` and `nightlogs`


# Observing Activities

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