---
sidebar: true
---

# Resources

Most resources exposed by `ArcsecondAPI` use the generic `ArcsecondAPIEndpoint` helpers.

## CRUD Operations

The common operations are:

- `list(**filters)`
- `read(id_or_uuid)`
- `create(...)`
- `update(id_or_uuid, ...)`
- `delete(id_or_uuid)`
- `find_one(**filters)`
- `upsert(match_field="name", ...)`

These methods are available on resources such as:

- `api.targets`
- `api.targetlists`
- `api.telescopes`
- `api.observations`
- `api.nightlogs`
- `api.datasets`
- `api.datafiles`
- `api.datapackages`
- `api.observingsites`
- `api.allskycameras`

## Generic CRUD Example

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig

config = ArcsecondConfig()
api = ArcsecondAPI(config)

dataset, error = api.datasets.create(
    name="My dataset",
    description="Created from Python",
)

if error:
    raise error

dataset, error = api.datasets.update(
    dataset["uuid"],
    description="Updated from Python",
)

datasets, error = api.datasets.list(page=1)
dataset, error = api.datasets.read(dataset["uuid"])
deleted, error = api.datasets.delete(dataset["uuid"])
```

## Create Or Update By Name

For many resources, `upsert()` is convenient when your script wants create-or-update
semantics:

```python
target, error = api.targets.upsert(
    name="M 42",
    ra_deg=83.82208,
    dec_deg=-5.39111,
)
```

## Planning Target Payloads

For targets, Arcsecond also exposes a pure helper that lets you inspect the resolution
result before creating or updating anything:

```python
from arcsecond import plan_target_payload

plan = plan_target_payload(
    name="51 Peg b",
    inferred_target_class="Exoplanet",
)

if not plan.is_valid:
    raise ValueError(plan.errors)

print(plan.payload)
print(plan.warnings)
```

The returned plan contains:

- `payload`: the backend-compatible payload you can pass to `api.targets.create(...)`
- `warnings`: non-blocking messages about overridden or ignored inferred values
- `errors`: blocking validation messages
- `is_valid`: `True` when the payload is safe to use

### Resolution Rules

The utility follows one simple precedence rule:

- user-provided values override inferred values

More precisely:

- If the user provides coordinates, the resulting payload becomes a manual `AstronomicalObject`
- If the user provides `target_class`, it overrides the inferred one
- If the user provides both coordinates and a non-`AstronomicalObject` class, the plan is invalid
- If the user provides neither coordinates nor `target_class`, you must infer the class first

### Examples

If the name suggests an exoplanet and no coordinates are provided:

```python
plan = plan_target_payload(
    name="51 Peg b",
    inferred_target_class="Exoplanet",
)

assert plan.payload == {
    "name": "51 Peg b",
    "target_class": "Exoplanet",
}
```

If the user provides coordinates, those take precedence and the payload becomes manual:

```python
plan = plan_target_payload(
    name="51 Peg b",
    coordinates={
        "right_ascension": 344.366,
        "declination": 20.768,
    },
    inferred_target_class="Exoplanet",
)

assert plan.payload["target_class"] == "AstronomicalObject"
assert plan.payload["mode"] == "manual"
```

If the user forces a non-manual-compatible class together with coordinates, the utility
returns an invalid plan:

```python
plan = plan_target_payload(
    name="51 Peg b",
    target_class="Exoplanet",
    coordinates={
        "right_ascension": 344.366,
        "declination": 20.768,
    },
)

assert plan.is_valid is False
```

## Targets

For Night Explorer related automation, prefer working with `targets` and `targetlists`.
The Night Explorer tree structure is richer and more UI-oriented, which makes it awkward
to manipulate directly from scripts.

The generic CRUD helpers are available on `api.targets`, so you do not have to build raw
JSON payloads yourself.

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

You can combine the planner with the target endpoint:

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig, plan_target_payload

config = ArcsecondConfig()
api = ArcsecondAPI(config)

plan = plan_target_payload(
    name="51 Peg b",
    inferred_target_class="Exoplanet",
)

if not plan.is_valid:
    raise ValueError(plan.errors)

target, error = api.targets.upsert(json=plan.payload)

if error:
    raise error
```

## Target Lists

`api.targetlists` supports the generic CRUD methods above, and also a few helpers for
managing the list membership.

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

The generic helpers are also available:

```python
lists_response, error = api.targetlists.list(page=1)
target_list, error = api.targetlists.read("a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a")
deleted, error = api.targetlists.delete("a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a")
```

## Target Lists With Planned Targets

When you import a target list from an external source, apply the same planning rule to
each individual target first, then create the list from the created target UUIDs.

```python
from arcsecond import ArcsecondAPI, ArcsecondConfig, plan_target_payload

config = ArcsecondConfig()
api = ArcsecondAPI(config)

candidates = [
    {"name": "M 42", "inferred_target_class": "AstronomicalObject"},
    {"name": "51 Peg b", "inferred_target_class": "Exoplanet"},
    {
        "name": "Custom field star",
        "coordinates": {
            "right_ascension": 15.5,
            "declination": -23.2,
        },
    },
]

target_ids = []
for candidate in candidates:
    plan = plan_target_payload(**candidate)
    if not plan.is_valid:
        raise ValueError(plan.errors)

    target, error = api.targets.upsert(json=plan.payload)
    if error:
        raise error

    target_ids.append(target["uuid"])

target_list, error = api.targetlists.create(
    name="Imported targets",
    targets=target_ids,
)
```

## Recommendation

For backend-side automation and imports related to Night Explorer, use:

- `api.targets` to create and maintain target records
- `api.targetlists` to group those targets for Night Explorer import flows

Avoid scripting against Night Explorer tree nodes unless you truly need UI-specific
behavior.
