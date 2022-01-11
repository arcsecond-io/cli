---
sidebar: true
---

## Install

Simply issue the following in a Terminal:

```bash
$ pip install arcsecond
```

To upgrade an existing Arcsecond installation:

```bash
$ pip install --upgrade arcsecond
```

The help is accessible like any other command line:

```bash
$ arcsecond --help
```

or, for subcommand

```bash
$ arcsecond <command> --help
````

At that point, you can access all the public resources of Arcsecond.io.

The Arcsecond CLI usage is similar to a utility like `git`. That is,
`arcsecond` is the main entry point, followed by a command. Most of the
commands are simply the name of API resources.


For accessing private resources, such as datasets, night logs etc, you must
log in (or register first).

## Setup

### Register to Arcsecond.io

You can register directly from the CLI:
```bash
$ arcsecond register
```
and provide a username and a password.

### Login to Arcsecond.io

**You must login first before accessing APIs.** 

```bash
$ arcsecond login 
```

To skip prompts:

```bash
$ arcsecond login --username <username> --password <password>
```

By registering or logging in, **your private API key will be stored locally** 
in the config file in `~/.arcsecond.ini`. **Do not share this key. It gives a
complete access to your private resources too.**

Logging in again will overwrite the current API key with the new one 
(assuming login is a success, of course).

If you think your key is compromised, you can regenerate one in your profile
settings in https://www.arcsecond.io. You cannot regenerate an API key with
the cli.
