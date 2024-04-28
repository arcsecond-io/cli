---
layout: home
title: Arcsecond CLI
description: Arcsecond CLI
hero:
  name: Arcsecond CLI
  tagline: The command-line utility / Python module to access the resources of Arcsecond.io, and easily upload your data to Arcsecond Cloud Storage.
  image:
    src: /img/logo-circle.png
    alt: Arcsecond CLI
footer: MIT Licensed | Copyright © 2018-present Arcsecond.io (F52 Tech).
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

Use the Access Key to have complete access to your resources. **Use
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

## Data Upload

### Using the CLI

The Arcsecond CLI makes it easy to upload files to your account or your observatory
portals.

**All non-hidden files will be uploaded.** Be careful to choose folders that
contain only data you want to send to the cloud. Of course, in case of a
mistake, the data can later on be deleted from the various Data pages
available on the web.

Here are the command for basic direct upload:

```bash
$ arcsecond upload [OPTIONS] <folder>
```

There are five `OPTIONS`:

* `-d <name or uuuid>` (or `--dataset <name or uuuid>`) to tell the CLI to what
  dataset all files of the folder (and its subfolders) must be put. The
  argument can either be a name or a UUID. If it is a name, Oort will try to
  find it. If none is found, Oort will create it. If it is a UUID, Oort will
  look for it. If none is found, Oort will raise an error.
* `-t <telescope uuid>` (or `--telescope <telescope uuid>`) to tell the CLI to 
  attach the dataset to a specific telescope (recommended). If none provided,
  a telescope can be chosen in the 'Datasets' webpage.
* `-p <subdomain>` (or `--portal <subdomain>`) to tell the CLI to send
  files to a portal.

The `upload` command will summarise its settings and ask for confirmation
before proceeding. It is a small step to ensure that no mistake have been
made before starting upload.

Use: `arcsecond datasets` to get a list of datasets already available.

### Using Python code

```python
from pathlib import Path
from arcsecond import ArcsecondConfig, UploadContext, FileUploader, walk_folder_and_upload

config = ArcsecondConfig() # it will read your config file.
context = UploadContext(config, 
                        dataset_uuid_or_name="<dataset uuid or name>", 
                        telescope_uuid="<telescope uuid or None>", 
                        org_subdomain="<portal subdomain or None>")
context.validate() # important step to perform before uploading.

# For uploading, there are two possibilities:

# 1. provide a folder, and let Arcsecond walk accross its content:
walk_folder_and_upload(context, "/folder/path/")

# 2. do it manually (no check for hidden files, and no estimation of sizes etc). 
root_path = Path('/folder/path')
for file_path in root_path.glob('**/*'):
    uploader = FileUploader(context, root_path, file_path, display_progress=True)
    status, substatus, error = uploader.upload_file()
```


## Arcsecond.io ?

Arcsecond.io is the Astronomical Observations Platform.

It is a unique and comprehensive cloud platform covering the complete observation's lifecycle,
for both individual astronomers and observatories, with a consistent set of capabilities:

(Note: the description below corresponds to the coming version V5 of Arcsecond planned for the next Solstice '24
in June).

- Explore: Use **Night Explorer** (a.k.a. iObserve) to easily identify which target are best suited for which night.
- Plan: Use our new **Night Plans** to carefully craft your future observing nights.
- Observe: Record your observing nights with **Night Logs**, and attach data to each observation.
- Store: Choose the industry-grade AWS-backed secured **Cloud Storage** of Arcsecond, or attach external ones.
- Distribute: Easily create **Data Packages** of your observations for sharing with peers or visiting observers.

Arcsecond is made by an astronomer for astronomers.
