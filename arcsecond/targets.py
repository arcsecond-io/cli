from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


TARGET_CLASS_ASTRONOMICAL_OBJECT = "AstronomicalObject"
TARGET_CLASS_EXOPLANET = "Exoplanet"
TARGET_CLASS_STANDARD_STAR = "StandardStar"
TARGET_CLASS_SOLAR_SYSTEM_PLANET = "SolarSystemPlanet"
TARGET_CLASS_SMALL_BODY = "SmallBody"
TARGET_CLASS_MICROLENSING = "Microlensing"
TARGET_CLASS_TRANSIENT = "Transient"

TARGET_CLASSES = {
    TARGET_CLASS_ASTRONOMICAL_OBJECT,
    TARGET_CLASS_EXOPLANET,
    TARGET_CLASS_STANDARD_STAR,
    TARGET_CLASS_SOLAR_SYSTEM_PLANET,
    TARGET_CLASS_SMALL_BODY,
    TARGET_CLASS_MICROLENSING,
    TARGET_CLASS_TRANSIENT,
}

TARGET_MODE_MANUAL = "manual"

TARGET_CLASSES_REQUIRING_NAME = {
    TARGET_CLASS_ASTRONOMICAL_OBJECT,
    TARGET_CLASS_EXOPLANET,
    TARGET_CLASS_STANDARD_STAR,
    TARGET_CLASS_SOLAR_SYSTEM_PLANET,
}

TARGET_CLASSES_REQUIRING_IDENTIFIER = {
    TARGET_CLASS_SMALL_BODY,
    TARGET_CLASS_MICROLENSING,
    TARGET_CLASS_TRANSIENT,
}


@dataclass(frozen=True)
class ArcsecondTargetPayloadPlan:
    payload: dict[str, Any]
    target_class: Optional[str]
    mode: str
    target_class_source: Optional[str]
    coordinates_source: Optional[str]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def _clean_string(value: Optional[str]) -> str:
    return (value or "").strip()


def _normalise_coordinates(coordinates: Optional[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
    if coordinates is None:
        return None
    return {
        key: value
        for key, value in dict(coordinates).items()
        if value is not None
    }


def _validate_target_class(target_class: str, label: str, errors: list[str]) -> None:
    if target_class and target_class not in TARGET_CLASSES:
        errors.append(f"{label} '{target_class}' is not a supported Arcsecond target class.")


def plan_target_payload(
    *,
    name: Optional[str] = None,
    identifier: Optional[str] = None,
    target_class: Optional[str] = None,
    coordinates: Optional[Mapping[str, Any]] = None,
    inferred_name: Optional[str] = None,
    inferred_identifier: Optional[str] = None,
    inferred_target_class: Optional[str] = None,
    color: Optional[str] = None,
    notes: Optional[str] = None,
    profile: Optional[str] = None,
    organisation: Optional[str] = None,
    extra_fields: Optional[Mapping[str, Any]] = None,
) -> ArcsecondTargetPayloadPlan:
    """
    Build a backend-compatible target payload while preserving the rule:
    user-provided values override inferred ones.

    This helper is pure: it does not perform network lookups or create/update targets.
    It simply turns user input plus optional inferred metadata into a target payload,
    warnings, and validation errors so callers can inspect the plan before applying it.
    """

    errors: list[str] = []
    warnings: list[str] = []

    user_name = _clean_string(name)
    user_identifier = _clean_string(identifier)
    user_target_class = _clean_string(target_class)

    inferred_name = _clean_string(inferred_name)
    inferred_identifier = _clean_string(inferred_identifier)
    inferred_target_class = _clean_string(inferred_target_class)

    _validate_target_class(user_target_class, "target_class", errors)
    _validate_target_class(inferred_target_class, "inferred_target_class", errors)

    effective_name = user_name or inferred_name
    effective_identifier = user_identifier or inferred_identifier
    effective_coordinates = _normalise_coordinates(coordinates)

    if not effective_name and not effective_identifier:
        errors.append("One of name or identifier must be provided.")

    if user_target_class and inferred_target_class and user_target_class != inferred_target_class:
        warnings.append(
            f"User-provided target_class '{user_target_class}' overrides inferred target_class '{inferred_target_class}'."
        )

    payload: dict[str, Any] = {}
    if effective_name:
        payload["name"] = effective_name
    if effective_identifier:
        payload["identifier"] = effective_identifier
    for key, value in {
        "color": color,
        "notes": notes,
        "profile": profile,
        "organisation": organisation,
    }.items():
        if value is not None:
            payload[key] = value
    if extra_fields:
        payload.update({key: value for key, value in dict(extra_fields).items() if value is not None})

    if effective_coordinates is not None:
        if user_target_class and user_target_class != TARGET_CLASS_ASTRONOMICAL_OBJECT:
            errors.append(
                "Manual coordinates are currently supported only for 'AstronomicalObject'. "
                f"Received target_class '{user_target_class}'."
            )

        effective_target_class = user_target_class or TARGET_CLASS_ASTRONOMICAL_OBJECT
        target_class_source = "user" if user_target_class else "default"
        coordinates_source = "user"

        if inferred_target_class and not user_target_class and inferred_target_class != TARGET_CLASS_ASTRONOMICAL_OBJECT:
            warnings.append(
                f"Inferred target_class '{inferred_target_class}' is ignored because user-provided coordinates "
                "require a manual 'AstronomicalObject' payload with the current backend."
            )

        if not effective_name:
            errors.append("Manual coordinates require a target name.")

        payload["target_class"] = effective_target_class
        payload["mode"] = TARGET_MODE_MANUAL
        payload["object"] = {
            "name": effective_name or effective_identifier,
            "equatorial_coordinates": effective_coordinates,
        }

        return ArcsecondTargetPayloadPlan(
            payload=payload,
            target_class=effective_target_class or None,
            mode=TARGET_MODE_MANUAL,
            target_class_source=target_class_source,
            coordinates_source=coordinates_source,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    effective_target_class = user_target_class or inferred_target_class
    target_class_source = None
    if user_target_class:
        target_class_source = "user"
    elif inferred_target_class:
        target_class_source = "inferred"

    if not effective_target_class:
        errors.append(
            "target_class could not be determined. Provide target_class explicitly, provide coordinates, "
            "or infer the class before creating/updating the target."
        )
    else:
        payload["target_class"] = effective_target_class

        if effective_target_class in TARGET_CLASSES_REQUIRING_NAME and not effective_name:
            errors.append(f"Target class '{effective_target_class}' requires a name.")

        if effective_target_class in TARGET_CLASSES_REQUIRING_IDENTIFIER and not effective_identifier:
            errors.append(f"Target class '{effective_target_class}' requires an identifier.")

    if effective_target_class and "object" not in payload:
        warnings.append(
            "This payload does not contain manual coordinates. Target creation will rely on the backend "
            "to resolve the object from name/identifier and target_class."
        )

    return ArcsecondTargetPayloadPlan(
        payload=payload,
        target_class=effective_target_class or None,
        mode="",
        target_class_source=target_class_source,
        coordinates_source=None,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )
