import click
import httpx
import machineid

from .utils import generate_password

CONTENT_TYPE = "application/vnd.api+json"


class KeygenClient(object):
    def __init__(self, config, email: str):
        self.__config = config
        self.__base_url = "https://api.keygen.sh/v1/accounts/arcsecond"
        self.__default_headers = {
            "Content-Type": CONTENT_TYPE,
            "Accept": CONTENT_TYPE,
        }
        self.__email = email

    def __generate_user_token(self):
        res = httpx.post(
            self.__base_url + "/tokens",
            headers={"Accept": CONTENT_TYPE},
            auth=(self.__email, self.__config.read_key("keygen_user_password")),
        )
        if res.status_code == 201:
            user_token = res.json().get("data").get("attributes").get("token")
            self.__config.save(keygen_user_token=user_token)
            return user_token, "OK"
        else:
            return None, "Cannot create user token"

    def __read_user(self):
        token, _ = self.__generate_user_token()
        headers = {**self.__default_headers}
        headers["Authorization"] = "Bearer " + token
        res = httpx.get(self.__base_url + "/users/" + self.__email, headers=headers)
        if res.status_code == 200:
            user_id = res.json().get("data").get("id")
            return user_id, "OK"
        else:
            return None, "User not found"

    def __create_user(self):
        keygen_user_id = self.__config.read_key("keygen_user_id")
        if keygen_user_id is not None:
            return keygen_user_id, "OK"

        keygen_user_password = self.__config.read_key("keygen_user_password")
        if keygen_user_password is None:
            keygen_user_password = generate_password()
            self.__config.save(keygen_user_password=keygen_user_password)

        res = httpx.post(
            self.__base_url + "/users",
            headers=self.__default_headers,
            json={
                "data": {
                    "type": "users",
                    "attributes": {
                        "firstName": "Awesome",
                        "lastName": "Astronomer",
                        "email": self.__email,
                        "password": keygen_user_password,
                    },
                }
            },
        )

        keygen_user_id = None
        if res.status_code == 201:
            keygen_user_id = res.json().get("data").get("id")
        else:
            errors = res.json().get("errors")
            if len(errors) == 1 and errors[0].get("code") == "EMAIL_TAKEN":
                keygen_user_id, msg = self.__read_user()

        if keygen_user_id is None:
            msg = "We are unable to create user, yet we cannot find your user id.\n"
            msg += "Please, contact team@arcsecond.io to fix the situation."
            return None, msg

        self.__config.save(keygen_user_id=keygen_user_id)
        return keygen_user_id, "OK"

    def __create_license(self, user_id):
        license_key = self.__config.read_key("keygen_license_key")
        if license_key:
            return license_key, "OK"

        # Obtaining a user token
        keygen_user_token = self.__config.read_key("keygen_user_token")
        if keygen_user_token is None:
            keygen_user_token, msg = self.__generate_user_token()
            if keygen_user_token is None:
                return None, "Impossible to get user token."

        headers = {**self.__default_headers}
        headers["Authorization"] = "Bearer " + keygen_user_token

        # Checking for an existing license.
        res = httpx.get(self.__base_url + "/licenses?limit=1", headers=headers)
        data = res.json().get("data")
        if len(data) == 1:
            license_id = data[0].get("id")
            license_key = data[0].get("attributes").get("key")
            self.__config.save(
                keygen_licence_id=license_id, keygen_license_key=license_key
            )
            return license_key, "OK"

        # We have no license, create one.
        policy_id = "2b2194d4-282e-4e3e-a39d-d01385cdf73e"
        res = httpx.post(
            self.__base_url + "/licenses",
            headers=headers,
            json={
                "data": {
                    "type": "licenses",
                    "relationships": {
                        "policy": {"data": {"type": "policies", "id": policy_id}},
                        "user": {"data": {"type": "users", "id": user_id}},
                    },
                }
            },
        )

        # TODO: deal with failure.
        data = res.json().get("data")
        license_id = data.get("id")
        license_key = data.get("attributes").get("key")
        self.__config.save(keygen_licence_id=license_id, keygen_license_key=license_key)

        return license_key, "OK"

    def __activate_license(self, license_key):
        machine_fingerprint = machineid.hashed_id()
        res = httpx.post(
            self.__base_url + "/licenses/actions/validate-key",
            headers=self.__default_headers,
            json={
                "meta": {
                    "key": license_key,
                    "scope": {"fingerprint": machine_fingerprint},
                }
            },
        )

        validation = res.json()
        if "errors" in validation:
            errs = validation["errors"]
            return False, "license validation failed: {}".format(
                ",".join(
                    map(
                        lambda e: "{} - {}".format(e["title"], e["detail"]).lower(),
                        errs,
                    )
                )
            )

        if validation["meta"]["valid"]:
            return True, "OK (license has already been activated on this machine)."

        # Otherwise, we need to determine why the current license is not valid,
        # because in our case it may be invalid because another machine has
        # already been activated, or it may be invalid because it doesn't
        # have any activated machines associated with it yet and in that case
        # we'll need to activate one.
        validation_code = validation["meta"]["code"]
        activation_is_required = (
            validation_code == "FINGERPRINT_SCOPE_MISMATCH"
            or validation_code == "NO_MACHINES"
            or validation_code == "NO_MACHINE"
        )

        if not activation_is_required:
            return False, "license {}".format(validation["meta"]["detail"])

        # If we've gotten this far, then our license has not been activated yet,
        # so we should go ahead and activate the current machine.
        headers = {**self.__default_headers}
        headers["Authorization"] = "License " + license_key
        res = httpx.post(
            self.__base_url + "/machines",
            headers=headers,
            json={
                "data": {
                    "type": "machines",
                    "attributes": {"fingerprint": machine_fingerprint},
                    "relationships": {
                        "license": {
                            "data": {
                                "type": "licenses",
                                "id": validation["data"]["id"],
                            }
                        }
                    },
                }
            },
        )

        activation = res.json()
        # If we get back an error, our activation failed.
        if "errors" in activation:
            errs = activation["errors"]
            return False, "Error: license activation failed: {}".format(
                ",".join(
                    map(
                        lambda e: "{} - {}".format(e["title"], e["detail"]).lower(),
                        errs,
                    )
                )
            )

        return True, "OK (license activated)"

    def setup_and_validate_license(self):
        user_id, msg = self.__create_user()
        if user_id is None:
            click.echo(msg)
            return False, msg

        license_key, msg = self.__create_license(user_id)
        if license_key is None:
            click.echo(msg)
            return False, msg

        status, msg = self.__activate_license(license_key)
        if not status:
            click.echo(msg)
            return False, msg

        return status, msg
