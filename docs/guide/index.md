---
sidebar: true
---

## CLI / Terminal

### Philosophy

The Arcsecond CLI is using the same principle as `git`. The main entry point
is `arcsecond` followed by a command. And most of the **commands have the 
name of API endpoints.**

For instance, to obtain the information about an object, and likewise, an exoplanet:

```bash
$ arcsecond objects "HD 5980"
$ arcsecond exoplanets "51 Peg b"
```

For objects, and exoplanets, you can open the webpage in the default browser:     

```bash
$ arcsecond objects "HD 5980" --open
$ arcsecond exoplanets "51 Peg b" --open
```

Or open the API webpage in the default browser for that object:     

```bash
$ arcsecond o "HD 5980" --open api
$ arcsecond exoplanets "51 Peg b" --open api
```

For other things, such as private observing runs and night logs, likewise:

```bash
$ arcsecond observingruns <uuid>
$ arcsecond nightlogs <uuid>    
```

### Available Endpoints

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

### Datasets and Data files

**You can entirely manage your datasets and Data/FITS files (including upload) from this CLI / Python module.**

To list your datasets (the two methods are identical, the second simply having its action name explicitly written):

```bash
$ arcsecond datasets
$ arcsecond datasets read
```

To create a dataset:

```bash
$ arcsecond datasets create --name "this is a new dataset"
```

To delete a dataset (**warning: this will also delete the associated data/FITS files!**):

```bash
$ arcsecond datasets delete <dataset uuid>
```

Data files are necessarily associated with a dataset. Hence a dataset UUID must be provided.
To upload a data file:

```bash
$ arcsecond datafiles <dataset uuid> create --file <path to a local data file>
```
    
To delete a data file, one use its "id/pk" (pk = Primary Key == ID):

```bash
$ arcsecond datafiles <dataset uuid> delete <Data file pk>
```

## Python Module

Using this as a Python module goes as follow

```python
>>> from arcsecond import ArcsecondAPI
>>> ArcsecondAPI.login(<username>, <password>)
>>> ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBJECTS).read('HD 5980')
```
