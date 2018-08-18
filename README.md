[![Build Status](https://img.shields.io/travis/arcsecond-io/cli.svg)](https://travis-ci.org/arcsecond-io/cli)
[![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)

# Arcsecond CLI

 Command-line interface (CLI) for arcsecond.io


# Installation

Simply run:

    $ pip install arcsecond

# Usage

Philosophy: the Arcsecond CLI is using the same principle as `git`: it has a global
command `arcsecond` followed by subcommands.

Help:

    $ arcsecond --help

**You must login first before accessing APIs.**

    $ arcsecond login 
    
To skip prompts:

    $ arcsecond login --username <username> --password <password>

Your private API key will be stored in the config file in `~/.arcsecond.ini`. Then, you can access public and private APIs. 

## Public APIs

For instance, to obtain the information about an object:

    $ arcsecond objects "HD 5980"
    
Likewise, it can be abbreviated, always by using the first letter.

     $ arcsecond o "HD 5980"
     
Open the webpage in the default browser for that object:     

     $ arcsecond o "HD 5980" --open

Open the API webpage in the default browser for that object:     

     $ arcsecond o "HD 5980" --open api

The available endpoints (and thus, subcommands) available so far are: `objects`, `exoplanets`, `findingcharts` and `profiles`.

## Private APIs

As of now, you can simply access your own fill profile:

    $ arcsecond me    

