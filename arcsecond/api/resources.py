from arcsecond.errors import ArcsecondError

from .endpoint import ArcsecondAPIEndpoint


class ArcsecondTargetListsResource(ArcsecondAPIEndpoint):
    """Target-list specific helpers built on top of the generic endpoint contract."""

    target_relation_key = "targets"
    target_writable_fields = (
        "id",
        "pk",
        "object",
        "name",
        "identifier",
        "target_class",
        "mode",
        "color",
        "notes",
        "tags",
        "profile",
        "organisation",
    )

    def _ensure_iterable(self, values):
        if values is None:
            return None
        if isinstance(values, dict):
            return [values]
        if isinstance(values, (str, int)):
            return [values]
        return list(values)

    def _target_payload_identity(self, target):
        if target.get("id") is not None:
            return ("id", target["id"])
        if target.get("pk") is not None:
            return ("pk", target["pk"])
        return (
            "composite",
            target.get("target_class"),
            target.get("identifier"),
            target.get("name"),
            target.get("mode"),
        )

    def _normalise_target_payloads(self, targets):
        values = self._ensure_iterable(targets)
        if values is None:
            return None

        payloads = []
        for target in values:
            if not isinstance(target, dict):
                raise ArcsecondError(
                    "Target list helpers expect target payload dictionaries, not scalar IDs or UUIDs. "
                    "Pass dictionaries such as `plan_target_payload(...).payload` or target objects returned "
                    "by `api.targets.read()/list()/upsert()`."
                )

            payload = {
                key: value
                for key, value in target.items()
                if key in self.target_writable_fields and value is not None
            }
            if not payload:
                raise ArcsecondError(
                    "Target dictionaries must include at least one writable target field."
                )

            payloads.append(payload)
        return payloads

    def _build_payload(self, json=None, targets=None, target_key=None, **fields):
        payload = super()._build_payload(json=json, **fields) or {}
        normalised_targets = self._normalise_target_payloads(targets)
        if normalised_targets is not None:
            payload[target_key or self.target_relation_key] = normalised_targets
        return payload or None

    def create(self, json=None, targets=None, target_key=None, **fields):
        payload = self._build_payload(
            json=json, targets=targets, target_key=target_key, **fields
        )
        return ArcsecondAPIEndpoint.create(self, json=payload)

    def update(self, id_name_uuid, json=None, targets=None, target_key=None, **fields):
        payload = self._build_payload(
            json=json, targets=targets, target_key=target_key, **fields
        )
        return ArcsecondAPIEndpoint.update(self, id_name_uuid, json=payload)

    def upsert(self, match_field="name", json=None, targets=None, target_key=None, **fields):
        payload = self._build_payload(
            json=json, targets=targets, target_key=target_key, **fields
        )
        return super().upsert(match_field=match_field, json=payload)

    def _read_target_refs(self, target_list, target_key=None):
        key = target_key or self.target_relation_key
        raw_targets = (target_list or {}).get(key, [])
        refs = self._normalise_target_payloads(raw_targets) or []
        return key, refs

    def set_targets(self, id_name_uuid, targets, target_key=None):
        target_key = target_key or self.target_relation_key
        return self.update(id_name_uuid, **{target_key: self._normalise_target_payloads(targets)})

    def clear_targets(self, id_name_uuid, target_key=None):
        return self.set_targets(id_name_uuid, [], target_key=target_key)

    def add_targets(self, id_name_uuid, targets, target_key=None):
        target_list, error = self.read(id_name_uuid)
        if error:
            return None, error

        key, current_refs = self._read_target_refs(target_list, target_key=target_key)
        current_identities = {
            self._target_payload_identity(target): target for target in current_refs
        }
        for target in self._normalise_target_payloads(targets) or []:
            identity = self._target_payload_identity(target)
            if identity not in current_identities:
                current_refs.append(target)
                current_identities[identity] = target
        return self.update(id_name_uuid, **{key: current_refs})

    def remove_targets(self, id_name_uuid, targets, target_key=None):
        target_list, error = self.read(id_name_uuid)
        if error:
            return None, error

        key, current_refs = self._read_target_refs(target_list, target_key=target_key)
        refs_to_remove = {
            self._target_payload_identity(target)
            for target in (self._normalise_target_payloads(targets) or [])
        }
        remaining_refs = [
            ref
            for ref in current_refs
            if self._target_payload_identity(ref) not in refs_to_remove
        ]
        return self.update(id_name_uuid, **{key: remaining_refs})

    def add_target(self, id_name_uuid, target, target_key=None):
        return self.add_targets(id_name_uuid, [target], target_key=target_key)

    def remove_target(self, id_name_uuid, target, target_key=None):
        return self.remove_targets(id_name_uuid, [target], target_key=target_key)
