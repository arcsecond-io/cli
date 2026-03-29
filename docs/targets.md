---
sidebar: true
---

# Targets And Target Lists

If you want to prepare content for Night Explorer from Python, prefer working with
`targets` and `targetlists`.

The Night Explorer tree structure is intentionally richer and more UI-oriented, which
makes it awkward to manipulate directly from scripts. Target lists are the better API
surface for imports and automation.

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

## Create Or Update Targets

The `targets` resource accepts keyword arguments directly, so you do not have to build
raw JSON payloads yourself.

```python
target, error = api.targets.upsert(
    name="M 42",
    ra_deg=83.82208,
    dec_deg=-5.39111,
    source_name="Orion Nebula",
)

if error:
    raise error
```

Use `create()` if you always want a new object, or `update()` if you already know the
UUID or identifier.

```python
target, error = api.targets.create(
    name="47 Tuc",
    ra_deg=6.023625,
    dec_deg=-72.08128,
)
```

```python
target, error = api.targets.update(
    "6d7f9f0b-2d67-4d3d-9e74-2d6d0e749b91",
    description="Globular cluster in Tucana",
)
```

## Create And Maintain Target Lists

You can create a target list and attach targets in the same call:

```python
target_list, error = api.targetlists.create(
    name="Tonight candidates",
    description="Targets imported for Night Explorer",
    targets=[
        "6d7f9f0b-2d67-4d3d-9e74-2d6d0e749b91",
        "c17cb272-5ed6-4a6f-a219-0ff4727863c2",
    ],
)

if error:
    raise error
```

To replace the full content of a list:

```python
target_list, error = api.targetlists.set_targets(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    [
        "6d7f9f0b-2d67-4d3d-9e74-2d6d0e749b91",
        "c17cb272-5ed6-4a6f-a219-0ff4727863c2",
    ],
)
```

To incrementally manage membership:

```python
target_list, error = api.targetlists.add_targets(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    ["c17cb272-5ed6-4a6f-a219-0ff4727863c2"],
)
```

```python
target_list, error = api.targetlists.remove_target(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    "c17cb272-5ed6-4a6f-a219-0ff4727863c2",
)
```

If you want create-or-update semantics for a list name:

```python
target_list, error = api.targetlists.upsert(
    name="Tonight candidates",
    description="Synced from Python",
    targets=["6d7f9f0b-2d67-4d3d-9e74-2d6d0e749b91"],
)
```

## Read And Delete

The generic REST helpers are still available:

```python
lists_response, error = api.targetlists.list(page=1)
target_list, error = api.targetlists.read("a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a")
deleted, error = api.targetlists.delete("a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a")
```

## Recommendation

For backend-side automation and imports, use:

- `api.targets` to create and maintain target records
- `api.targetlists` to group those targets for Night Explorer import flows

Avoid scripting against Night Explorer tree nodes unless you truly need UI-specific
behavior.
