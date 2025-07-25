from urllib.parse import urlencode

import click
import httpx

from arcsecond.api.config import ArcsecondConfig
from arcsecond.api.constants import API_AUTH_PATH_VERIFY, API_AUTH_PATH_VERIFY_PORTAL
from arcsecond.errors import ArcsecondError

SAFE_METHODS = ["GET", "OPTIONS"]
WRITABLE_MEMBERSHIPS = ["superadmin", "admin", "member"]


class ArcsecondAPIEndpoint(object):
    def __init__(
        self,
        config: ArcsecondConfig,
        path: str,
        subdomain: str = "",
    ):
        self.__config = config
        self.__path = path
        self.__subdomain = subdomain

    @property
    def path(self):
        return self.__path

    def _get_base_url(self):
        if not self.__config.api_server:
            raise ArcsecondError(
                f"API server address for name '{self.__config.api_name}' is unknown/invalid."
            )
        url = self.__config.api_server
        if not url.endswith("/"):
            url += "/"
        return url

    def _build_url(self, *args, **filters):
        fragments = [
            f
            for f in [
                self.__subdomain,
            ]
            + list(args)
            if f and len(f) > 0
        ]
        url = self._get_base_url() + "/".join(fragments)
        if not url.endswith("/"):
            url += "/"
        query = "?" + urlencode(filters) if len(filters) > 0 else ""
        return url + query

    def _list_url(self, **filters):
        return self._build_url(self.__path, **filters)

    def _detail_url(self, uuid_or_id):
        return self._build_url(self.__path, str(uuid_or_id))

    def list(self, **filters):
        return self._perform_request(self._list_url(**filters), "get")

    def read(self, id_name_uuid, headers=None):
        return self._perform_request(
            self._detail_url(id_name_uuid), "get", headers=headers
        )

    def create(self, json=None, files=None, headers=None):
        return self._perform_request(
            self._list_url(), "post", json=json, files=files, headers=headers
        )

    def update(self, id_name_uuid, json=None, files=None, headers=None):
        return self._perform_request(
            self._detail_url(id_name_uuid),
            "patch",
            json=json,
            files=files,
            headers=headers,
        )

    def delete(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), "delete")

    def _perform_request(self, url, method_name, json=None, files=None, headers=None):
        if self.__config.verbose:
            click.echo(f"Sending {method_name} request to {url}")

        headers = self._check_and_set_auth_key(headers or {}, url)
        method = getattr(httpx, method_name.lower())

        kwargs = {"headers": headers, "timeout": 60}
        if files and json:
            # Do NOT set json=json, keep data=json, to avoid overriding Content-Type with `application/json`.
            kwargs.update(files=files, data=json)
        elif json and not files:
            kwargs.update(json=json)
        elif files and not json:
            raise ArcsecondError("Files but no json?")

        try:
            response = method(url, **kwargs)
        except httpx.RequestError as exc:
            return None, ArcsecondError(str(exc), 400)
        else:
            if isinstance(response, dict):
                # Responses of standard JSON payload requests are dict
                return response, None
            elif response is not None:
                if 200 <= response.status_code < 300:
                    return response.json() if response.text else {}, None
                else:
                    return None, ArcsecondError(response.text, response.status_code)
            else:
                return None, ArcsecondError("Response is None", -1)

    def _check_and_set_auth_key(self, headers, url):
        # No token header for login and register
        if (
            API_AUTH_PATH_VERIFY in url
            or API_AUTH_PATH_VERIFY_PORTAL in url
            or "Authorization" in headers.keys()
        ):
            return headers

        if self.__config.verbose:
            click.echo("Checking local API|Upload key... ", nl=False)

        # Choose the strongest key first
        auth_key = self.__config.access_key or self.__config.upload_key

        if not auth_key:
            raise ArcsecondError(
                "Missing auth keys (API or Upload). You must login first: $ arcsecond login"
            )

        headers["X-Arcsecond-API-Authorization"] = "Key " + auth_key

        if self.__config.verbose:
            key_str = auth_key[:3] + 9 * "*"
            click.echo(f"'X-Arcsecond-API-Authorization' = 'Key {key_str}'")

        return headers
