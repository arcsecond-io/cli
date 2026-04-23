---
sidebar: true
---

# API Basics

The Arcsecond CLI can also be used as a Python module.

## Setup

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig

config = ArcsecondConfig()
api = ArcsecondAPI(config)
```

If you are targeting an observatory portal, pass its subdomain:

```python
api = ArcsecondAPI(config, subdomain="my-observatory")
```

On a self-hosted Arcsecond.local install, the subdomain is always `"local"`:

```python
api = ArcsecondAPI(config, subdomain="local")
```

## Authentication

Authentication with the Python module currently relies on your Arcsecond keys.

### Reuse CLI credentials

Login once from the command line:

```bash
arcsecond login
```

This stores your credentials locally in `~/.config/arcsecond/config.ini`, which
`ArcsecondConfig()` will load automatically.

To skip prompts:

```bash
arcsecond login --username <username> --type access --key <access-key>
```

or:

```bash
arcsecond login --username <username> --type upload --key <upload-key>
```

Once that is done, Python code can reuse the stored configuration:

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig

config = ArcsecondConfig()
api = ArcsecondAPI(config)
```

### Authenticate in Python code

You can also authenticate directly in Python code:

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig

config = ArcsecondConfig()
api = ArcsecondAPI(config)

status, error = api.login(
    username="my-username",
    access_key="my-access-key",
)

if error:
    raise error
```

For upload-only workflows, use an Upload Key instead:

```python
status, error = api.login(
    username="my-username",
    upload_key="my-upload-key",
)
```

Important: Access Keys are powerful and are not scoped. Use them only in trusted
backend or local automation contexts, never in browser-side code.

For Python scripts that only need to upload data, prefer an Upload Key. For broader
resource management, use an Access Key.

## Next Step

Once authenticated, move to [Resources](/resources) for the generic CRUD helpers,
target planning utilities, and target list management helpers.
