---
sidebar: true
---

# Resources

Most resources exposed by `ArcsecondAPI` use the generic `ArcsecondAPIEndpoint` helpers.
Start by configuring `ArcsecondAPI` as described in [API Basics](/api-basics).

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
dataset, error = api.datasets.upsert(
    name="My dataset",
    description="Synced from Python",
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
    name="51 Peg b",
    target_class="Exoplanet",
)
```

```python
target, error = api.targets.update(
    42,
    notes="Globular cluster in Tucana",
)
```

```python
plan = plan_target_payload(
    name="M 42",
    inferred_target_class="AstronomicalObject",
)

target, error = api.targets.upsert(json=plan.payload)

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

Targets are managed through integer target IDs on `api.targets`, but target lists
themselves are managed through UUIDs on `api.targetlists`.

When you create or update a target list, the `targets` field must contain target
payload dictionaries, not target IDs or UUIDs. The easiest inputs are:

- payloads returned by `plan_target_payload(...).payload`
- target objects returned by `api.targets.read()`, `api.targets.list()`, or `api.targets.upsert()`

You can create a target list and attach targets in the same call:

```python
from arcsecond import plan_target_payload

m42 = plan_target_payload(
    name="M 42",
    inferred_target_class="AstronomicalObject",
).payload

pegb = plan_target_payload(
    name="51 Peg b",
    inferred_target_class="Exoplanet",
).payload

target_list, error = api.targetlists.create(
    name="Tonight candidates",
    description="Targets imported for Night Explorer",
    targets=[m42, pegb],
)

if error:
    raise error
```

To replace the full content of a list:

```python
target_a, error = api.targets.read(42)
target_b, error = api.targets.read(314)

target_list, error = api.targetlists.set_targets(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    [target_a, target_b],
)
```

To incrementally manage membership:

```python
target_list, error = api.targetlists.add_targets(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    [
        plan_target_payload(
            name="M 31",
            inferred_target_class="AstronomicalObject",
        ).payload
    ],
)
```

```python
target_list, error = api.targetlists.remove_target(
    "a0e974a6-6f2d-4b7a-b9d2-3a3f7d7ef61a",
    target_b,
)
```

If you want create-or-update semantics for a list name:

```python
target_a, error = api.targets.read(42)

target_list, error = api.targetlists.upsert(
    name="Tonight candidates",
    description="Synced from Python",
    targets=[target_a],
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
each individual target first, then create the list from the resulting target payloads.

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

targets = []
for candidate in candidates:
    plan = plan_target_payload(**candidate)
    if not plan.is_valid:
        raise ValueError(plan.errors)

    target, error = api.targets.upsert(json=plan.payload)
    if error:
        raise error

    targets.append(target)

target_list, error = api.targetlists.create(
    name="Imported targets",
    targets=targets,
)
```

## Recommendation

For backend-side automation and imports related to Night Explorer, use:

- `api.targets` to create and maintain target records
- `api.targetlists` to group those targets for Night Explorer import flows

Avoid scripting against Night Explorer tree nodes unless you truly need UI-specific
behavior.
