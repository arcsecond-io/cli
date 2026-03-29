from arcsecond.errors import ArcsecondError

from .endpoint import ArcsecondAPIEndpoint


class ArcsecondTargetListsResource(ArcsecondAPIEndpoint):
    """Target-list specific helpers built on top of the generic endpoint contract."""

    target_relation_keys = ("targets", "target_uuids", "target_ids")

    def _ensure_iterable(self, values):
        if values is None:
            return None
        if isinstance(values, (str, int)):
            return [values]
        return list(values)

    def _normalise_target_references(self, targets):
        values = self._ensure_iterable(targets)
        if values is None:
            return None

        refs = []
        for target in values:
            if isinstance(target, dict):
                ref = (
                    target.get("uuid")
                    or target.get("id")
                    or target.get("pk")
                    or target.get("name")
                )
                if ref is None:
                    raise ArcsecondError(
                        "Target dictionaries must include one of: uuid, id, pk or name."
                    )
                refs.append(ref)
            else:
                refs.append(target)
        return refs

    def _target_key_from_payload(self, payload, target_key=None):
        if target_key:
            return target_key
        for key in self.target_relation_keys:
            if payload and key in payload:
                return key
        return self.target_relation_keys[0]

    def _build_payload(self, json=None, targets=None, target_key=None, **fields):
        payload = super()._build_payload(json=json, **fields) or {}
        normalised_targets = self._normalise_target_references(targets)
        if normalised_targets is not None:
            payload[self._target_key_from_payload(payload, target_key=target_key)] = (
                normalised_targets
            )
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
        key = self._target_key_from_payload(target_list or {}, target_key=target_key)
        raw_targets = (target_list or {}).get(key, [])
        refs = self._normalise_target_references(raw_targets) or []
        return key, refs

    def set_targets(self, id_name_uuid, targets, target_key=None):
        target_key = self._target_key_from_payload({}, target_key=target_key)
        return self.update(id_name_uuid, **{target_key: self._normalise_target_references(targets)})

    def clear_targets(self, id_name_uuid, target_key=None):
        return self.set_targets(id_name_uuid, [], target_key=target_key)

    def add_targets(self, id_name_uuid, targets, target_key=None):
        target_list, error = self.read(id_name_uuid)
        if error:
            return None, error

        key, current_refs = self._read_target_refs(target_list, target_key=target_key)
        for ref in self._normalise_target_references(targets) or []:
            if ref not in current_refs:
                current_refs.append(ref)
        return self.update(id_name_uuid, **{key: current_refs})

    def remove_targets(self, id_name_uuid, targets, target_key=None):
        target_list, error = self.read(id_name_uuid)
        if error:
            return None, error

        key, current_refs = self._read_target_refs(target_list, target_key=target_key)
        refs_to_remove = set(self._normalise_target_references(targets) or [])
        remaining_refs = [ref for ref in current_refs if ref not in refs_to_remove]
        return self.update(id_name_uuid, **{key: remaining_refs})

    def add_target(self, id_name_uuid, target, target_key=None):
        return self.add_targets(id_name_uuid, [target], target_key=target_key)

    def remove_target(self, id_name_uuid, target, target_key=None):
        return self.remove_targets(id_name_uuid, [target], target_key=target_key)
