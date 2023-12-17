import json
import os

import click
import requests

from arcsecond import Config


class KeygenClient(object):
    def __init__(self, state, do_try):
        self.__config = Config(state)
        self.__section_name = 'keygen:try' if do_try else 'keygen'
        self.__base_url = "https://api.keygen.sh/v1/accounts/arcsecond-io"
        self.__default_headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json"
        }

    def __config_save(self, **kwargs):
        kwargs.update(section=self.__section_name)
        self.__config.save(**kwargs)

    def get_user_id(self):
        self.__config.read_key('user', self.__section_name)

    def create_user(self, arcsecond_profile):
        user_id = self.get_user_id()
        if user_id is not None:
            return user_id
        res = requests.post(
            self.__base_url + "/users",
            headers=self.__default_headers,
            data=json.dumps({
                "data": {
                    "type": "users",
                    "attributes": {
                        "firstName": arcsecond_profile.get('first_name', 'Famous') or "Famous",
                        "lastName": arcsecond_profile.get('last_name', 'Astronomer') or "Astronomer",
                        "email": arcsecond_profile.get('email'),
                        "password": None  # passwordless user
                    }
                }
            })
        )
        if res.status_code != 201:
            click.echo('We are unable to create user, yet we cannot find your user id.')
            click.echo('Please, contact cedric@arcsecond.io to fix the situation.')
            return
        user_id = res.json().get('data').get('id')
        self.__config_save(user=user_id, email=arcsecond_profile.get('email'))
        return user_id

    def create_license(self):
        user_id = self.get_user_id()
        if user_id is not None:
            return None
        product_id = 'cf22a770-6252-44c2-b1ad-acd9dccad9ff'
        policy_id = '8cecf79e-35b4-40fb-848b-31b0c19455ba'
        headers = {**self.__default_headers}
        headers['Authorization'] = "Bearer " + product_id
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
        print(res.json())

    def activate_license(license_key):
        machine_fingerprint = machineid.hashed_id('arcsecond')
        validation = requests.post(
            "https://api.keygen.sh/v1/accounts/{}/licenses/actions/validate-key".format(
                os.environ['KEYGEN_ACCOUNT_ID']),
            headers={
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json"
            },
            data=json.dumps({
                "meta": {
                    "scope": {"fingerprint": machine_fingerprint},
                    "key": license_key
                }
            })
        ).json()

        if "errors" in validation:
            errs = validation["errors"]

            return False, "license validation failed: {}".format(
                ','.join(map(lambda e: "{} - {}".format(e["title"], e["detail"]).lower(), errs))
            )

        # If the license is valid for the current machine, that means it has
        # already been activated. We can return early.
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
        activation = requests.post(
            "https://api.keygen.sh/v1/accounts/{}/machines".format(os.environ['KEYGEN_ACCOUNT_ID']),
            headers={
                "Authorization": "License {}".format(license_key),
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json"
            },
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
        ).json()

        # If we get back an error, our activation failed.
        if "errors" in activation:
            errs = activation["errors"]

            return False, "license activation failed: {}".format(
                ','.join(map(lambda e: "{} - {}".format(e["title"], e["detail"]).lower(), errs))
            )

        return True, "license activated"

    # Run from the command line:
