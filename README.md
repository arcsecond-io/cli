[![Build Status](https://img.shields.io/travis/onekiloparsec/arcsecond-python.svg)](https://travis-ci.org/onekiloparsec/arcsecond-python.svg?branch=master)

# Arcsecond CLI

 Command-line interface (CLI) for arcsecond.io


# Installation

Simply run:

    $ pip install arcsecond


# Usage

Philosophy: the Arcsecond CLI is using the same principle as `git`: it has a global
command `arcsecond` followed by subcommands, such as `objects`, or `exoplanets`.

For instance, to obtain the information about an object:

    $ arcsecond objects "HD 5980"
    
Likewise, it can be abbreviated:

     $ arcsecond o "HD 5980"
     
Open the webpage in the default browser for that object (`--open` can be abbreviated `-o`):     

     $ arcsecond o "HD 5980" --open

Open the API webpage in the default browser for that object (`--open` can be abbreviated `-o`):     

     $ arcsecond o "HD 5980" --open api

Help:

    $ arcsecond --help

