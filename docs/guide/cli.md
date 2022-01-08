# CLI a.k.a. Terminal Mode

The Arcsecond CLI usage is similar to a command like `git`, that is,
`arcsecond` is the main command, followed by a subcommand. Most of the
subcommands are simply the name of API resources.

Then help is accessible like any other command line:

```bash
$ arcsecond --help
```

or 

```bash
$ arcsecond <command> --help
````

However, the first thing to do is to login / register.

## Register to Arcsecond.io

You can register directly from the CLI:
```bash
$ arcsecond register
```
and provide a username and a password.

## Login to Arcsecond.io

**You must login first before accessing APIs.** 
This is for making easy to access private APIs, but also for server logging,
and to better understand the usage that is made of our APIs.

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
