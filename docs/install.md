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

The Arcsecond CLI usage is similar to a utility like `git`. That is,
`arcsecond` is the main entry point, followed by a command. Most of the
commands are simply the name of API resources.

## Setup

To use the CLI, you need an Arcsecond account (it is entirely free to
create one). In your Settings page in https://www.arcsecond.io you will
find your Access Key and your Upload Key. They give a different access
level to your resources.

Use the Access Key to have a complete access to your resources. **Use
your Access Key only on trusted computers.**. If you simply want to
use the CLI for uploading files, use the Upload Key, which has just enough
permissions to upload data to your account, or your observatory portals.

Then, you can login, providing answers to the prompts.

```bash
$ arcsecond login 
```

To skip prompts:

```bash
$ arcsecond login --username <username> --upload_key <key>
```

By logging in, **your private Access key or your Upload Key will be stored locally**
in the config file in `~/.config/arcsecond/config.ini`.

Logging in again will overwrite the current key with the new one
(assuming login is a success, of course).

If you think your key is compromised, you can regenerate one in your profile
settings in https://www.arcsecond.io. You cannot regenerate a key with
the cli.
