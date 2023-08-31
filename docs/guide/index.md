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
$ arcsecond observingsites <uuid>
$ arcsecond telescopes <uuid>
```

### Available Endpoints

The available **read-only** API endpoints (and thus, subcommands) available so far are: 
* `observingsites`, `telescopes` and `instruments` (public)
* `organisations`, `members`, `uploadkeys` (private)
* `me` (personal profile, private)

## Python Module

Using this as a Python module goes as follow

```python
>>> from arcsecond import ArcsecondAPI
>>> ArcsecondAPI.login(<username>, <password>)
>>> ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBJECTS).read('HD 5980')
```
