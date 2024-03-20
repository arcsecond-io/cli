import json

import click
import machineid
import requests

from .utils import generate_password


class KeygenClient(object):
    def __init__(self, config, do_try, profile):
        self.__config = config
        self.__section_name = 'keygen:try' if do_try else 'keygen'
        self.__base_url = "https://api.keygen.sh/v1/accounts/arcsecond-io"
        self.__default_headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }
        self.__profile = profile

    def __config_save(self, **kwargs):
        kwargs.update(section=self.__section_name)
        self.__config.save(**kwargs)

    def __config_get(self, key):
        return self.__config.read_key(key, self.__section_name)

    def __create_user(self):
        user_id = self.__config_get('user_id')
        if user_id is not None:
            return user_id, 'OK'

        email = self.__profile.get('email')
        password = generate_password()
        self.__config_save(password=password, email=email)

        res = requests.post(
            self.__base_url + "/users",
            headers=self.__default_headers,
            data=json.dumps({
                "data": {
                    "type": "users",
                    "attributes": {
                        "firstName": self.__profile.get('first_name', 'Famous') or "Famous",
                        "lastName": self.__profile.get('last_name', 'Astronomer') or "Astronomer",
                        "email": email,
                        "password": password
                    }
                }
            })
        )

        if res.status_code != 201:
            msg = 'We are unable to create user, yet we cannot find your user id.\n'
            msg += 'Please, contact cedric@arcsecond.io to fix the situation.'
            return None, msg

        data = res.json().get('data')
        user_id = data.get('id')
        self.__config_save(user_id=user_id)

        return user_id, 'OK'

    def _generate_user_token(self):
        email, password = self.__config_get('email'), self.__config_get('password')
        res = requests.post(
            self.__base_url + "/tokens",
            headers={"Accept": "application/vnd.api+json"},
            auth=(email, password)
        )
        data = res.json().get('data')
        user_token = data.get('attributes').get('token')
        self.__config_save(user_token=user_token)
        return user_token, 'OK'

    def __create_license(self, user_id):
        license_key = self.__config_get('license_key')
        if license_key:
            return license_key, 'OK'

        user_token, msg = self._generate_user_token()
        res = requests.get(
            self.__base_url + "/licenses?limit=1",
            headers={
                "Accept": "application/vnd.api+json",
                "Authorization": "Bearer " + user_token
            }
        )

        data = res.json().get('data')
        if len(data) == 1:
            license_id = data[0].get('id')
            license_key = data[0].get('attributes').get('key')
            self.__config_save(licence_id=license_id, license_key=license_key)
            return license_key, 'OK'

        policy_id = '8cecf79e-35b4-40fb-848b-31b0c19455ba'
        headers = {**self.__default_headers}
        headers['Authorization'] = "Bearer " + user_token
        res = requests.post(
            self.__base_url + "/licenses",
            headers=headers,
            data=json.dumps({
                "data": {
                    "type": "licenses",
                    "relationships": {
                        "policy": {
                            "data": {"type": "policies", "id": policy_id}
                        },
                        "user": {
                            "data": {"type": "users", "id": user_id}
                        }
                    }
                }
            })
        )

        # TODO: deal with failure.
        data = res.json().get('data')
        license_id = data.get('id')
        license_key = data.get('attributes').get('key')
        self.__config_save(licence_id=license_id, license_key=license_key)

        return license_key, 'OK'

    def __activate_license(self, license_key):
        machine_fingerprint = machineid.hashed_id()
        res = requests.post(
            self.__base_url + "/licenses/actions/validate-key",
            headers=self.__default_headers,
            data=json.dumps({
                "meta": {
                    "key": license_key,
                    "scope": {
                        "fingerprint": machine_fingerprint
                    }
                }
            })
        )

        validation = res.json()
        if "errors" in validation:
            errs = validation["errors"]
            return False, "license validation failed: {}".format(
                ','.join(map(lambda e: "{} - {}".format(e["title"], e["detail"]).lower(), errs))
            )

        if validation["meta"]["valid"]:
            return True, "license has already been activated on this machine"

        # Otherwise, we need to determine why the current license is not valid,
        # because in our case it may be invalid because another machine has
        # already been activated, or it may be invalid because it doesn't
        # have any activated machines associated with it yet and in that case
        # we'll need to activate one.
        validation_code = validation["meta"]["code"]
        activation_is_required = validation_code == 'FINGERPRINT_SCOPE_MISMATCH' or \
                                 validation_code == 'NO_MACHINES' or \
                                 validation_code == 'NO_MACHINE'

        if not activation_is_required:
            return False, "license {}".format(validation["meta"]["detail"])

        # If we've gotten this far, then our license has not been activated yet,
        # so we should go ahead and activate the current machine.
        headers = {**self.__default_headers}
        headers['Authorization'] = "License " + license_key
        res = requests.post(
            self.__base_url + "/machines",
            headers=headers,
            data=json.dumps({
                "data": {
                    "type": "machines",
                    "attributes": {
                        "fingerprint": machine_fingerprint
                    },
                    "relationships": {
                        "license": {
                            "data": {"type": "licenses", "id": validation["data"]["id"]}
                        }
                    }
                }
            })
        )

        activation = res.json()
        # If we get back an error, our activation failed.
        if "errors" in activation:
            errs = activation["errors"]
            return False, "license activation failed: {}".format(
                ','.join(map(lambda e: "{} - {}".format(e["title"], e["detail"]).lower(), errs))
            )

        return True, "license activated"

    def setup_and_validate_license(self):
        user_id, msg = self.__create_user()
        if user_id is None:
            click.echo(msg)
            return

        license_key, msg = self.__create_license(user_id)
        if license_key is None:
            click.echo(msg)
            return

        status, msg = self.__activate_license(license_key)
        return status, msg
