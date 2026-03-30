---
sidebar: true
---

# Install & Login

Simply issue the following in a Terminal:

```bash
pip install arcsecond
```

To upgrade an existing Arcsecond installation:

```bash
pip install --upgrade arcsecond
```

The help is available like any other command-line tool:

```bash
arcsecond --help
```

For subcommands:

```bash
arcsecond <command> --help
```

The Arcsecond CLI works like a tool such as `git`: `arcsecond` is the main entry
point, followed by a command. Many commands directly map to Arcsecond resources.

## Authentication

To use the CLI, you need an Arcsecond account. In your settings page on
[arcsecond.io](https://www.arcsecond.io) you will find two kinds of credentials:

- an Access Key for broad access to your resources
- an Upload Key for upload-only workflows

Use an Access Key only on trusted computers. If you only need to upload files,
prefer an Upload Key.

### Interactive login

Run:

```bash
arcsecond login
```

The CLI will prompt for:

- `username`
- `type` (`access` or `upload`)
- `key`

Your credential is stored locally in `~/.config/arcsecond/config.ini`.

### Non-interactive login

To skip prompts, pass all values explicitly:

```bash
arcsecond login --username <username> --type access --key <access-key>
```

or:

```bash
arcsecond login --username <username> --type upload --key <upload-key>
```

Logging in again overwrites the stored credential if the login succeeds.

If you think a key is compromised, regenerate it from your profile settings on
[arcsecond.io](https://www.arcsecond.io). The CLI cannot regenerate keys for you.
