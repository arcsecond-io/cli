from arcsecond import ArcsecondTargetPayloadPlan, plan_target_payload


def test_plan_target_payload_uses_manual_astroobject_when_coordinates_are_provided():
    plan = plan_target_payload(
        name="51 Peg b",
        coordinates={"right_ascension": 344.366, "declination": 20.768},
        inferred_target_class="Exoplanet",
    )

    assert isinstance(plan, ArcsecondTargetPayloadPlan)
    assert plan.is_valid is True
    assert plan.target_class == "AstronomicalObject"
    assert plan.mode == "manual"
    assert plan.payload["target_class"] == "AstronomicalObject"
    assert plan.payload["mode"] == "manual"
    assert plan.payload["object"]["equatorial_coordinates"] == {
        "right_ascension": 344.366,
        "declination": 20.768,
    }
    assert "ignored" in plan.warnings[0]


def test_plan_target_payload_rejects_non_astro_manual_coordinates():
    plan = plan_target_payload(
        name="51 Peg b",
        target_class="Exoplanet",
        coordinates={"right_ascension": 344.366, "declination": 20.768},
    )

    assert plan.is_valid is False
    assert "Manual coordinates are currently supported only for 'AstronomicalObject'." in plan.errors[0]


def test_plan_target_payload_uses_user_target_class_over_inferred_one():
    plan = plan_target_payload(
        name="51 Peg b",
        target_class="AstronomicalObject",
        inferred_target_class="Exoplanet",
    )

    assert plan.is_valid is True
    assert plan.target_class == "AstronomicalObject"
    assert plan.payload["target_class"] == "AstronomicalObject"
    assert "overrides inferred target_class" in plan.warnings[0]


def test_plan_target_payload_requires_identifier_for_small_bodies():
    plan = plan_target_payload(
        name="Ceres",
        target_class="SmallBody",
    )

    assert plan.is_valid is False
    assert "requires an identifier" in plan.errors[0]


def test_plan_target_payload_accepts_inferred_identifier_for_small_bodies():
    plan = plan_target_payload(
        name="Ceres",
        target_class="SmallBody",
        inferred_identifier="2000001",
    )

    assert plan.is_valid is True
    assert plan.payload["identifier"] == "2000001"
    assert plan.payload["target_class"] == "SmallBody"


def test_plan_target_payload_requires_target_class_or_coordinates():
    plan = plan_target_payload(name="M42")

    assert plan.is_valid is False
    assert "target_class could not be determined" in plan.errors[0]


def test_plan_target_payload_accepts_inferred_target_class_without_coordinates():
    plan = plan_target_payload(
        name="M42",
        inferred_target_class="AstronomicalObject",
    )

    assert plan.is_valid is True
    assert plan.target_class == "AstronomicalObject"
    assert plan.mode == ""
    assert plan.payload["target_class"] == "AstronomicalObject"
