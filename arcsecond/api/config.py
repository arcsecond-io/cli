import os
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

from arcsecond.errors import ArcsecondError
from arcsecond.options import State

from .constants import ARCSECOND_API_URL_PROD

# Where the configuration lives, when it is not to live in the usual place.
#
# Set this to keep several sets of credentials apart — a personal account and
# an observatory's, say — or to point a container or a CI job at a directory of
# its own. It is also what the test suite uses: the tests write real-looking
# credentials, and without somewhere else to put them they would land in the
# developer's own config file and stay there.
#
# An environment variable rather than something passed in, because the CLI
# starts child processes of its own (`arcsecond proxy start`), and those have
# to end up in the same place as the command that started them.
CONFIG_DIR_ENV_VAR = "ARCSECOND_CONFIG_DIR"

# Which API server the CLI talks to, when a command does not say.
#
# Every registered server has a section of its own in config.ini — its
# address and the credentials for it together — and this is the name of the
# one currently pointed at. It is set with `arcsecond api use <name>` and
# stays set: every later command uses it, so nobody has to type a server on
# each one. The environment variable is the one-shot override for scripts and
# cron jobs, which should not move the pointer of whoever sits at the keyboard.
API_NAME_ENV_VAR = "ARCSECOND_API"
DEFAULT_API_NAME = "cloud"

# The section that holds the CLI's own settings (the pointer above, the
# remembered Arcsecond.local install directory...). It is not an API server and
# must never be read as one. Not configparser's DEFAULT section: values placed
# there leak into every other section.
CLI_SECTION = "cli"
CLI_KEY_API = "api"


class ArcsecondConfig(object):
    def __init__(self, **kwargs):
        api_name = kwargs.get("api_name") or ArcsecondConfig.current_api_name()
        if api_name == CLI_SECTION:
            raise ArcsecondError(f"'{CLI_SECTION}' is reserved and cannot name an API.")
        self.__api_name = api_name
        self.__verbose = kwargs.get("verbose", 0) or 0
        if "config" in kwargs.keys():
            self.__config = kwargs.get("config")
        else:
            self.__config = ConfigParser()
            self.__config.read(str(ArcsecondConfig.file_path()))
            if self.__api_name not in self.__config.sections():
                self.__config.add_section(self.__api_name)
        self.__section = self.__config[self.__api_name]

    @classmethod
    def from_state(cls, state: State):
        return cls(api_name=state.api_name, verbose=state.verbose)

    # ------------------------------------------------------------------
    # The CLI's own settings: the API pointer and friends
    # ------------------------------------------------------------------

    @classmethod
    def _read_parser(cls) -> ConfigParser:
        parser = ConfigParser()
        parser.read(str(cls.file_path()))
        return parser

    @classmethod
    def _write_parser(cls, parser: ConfigParser) -> None:
        with open(cls.file_path(), "w") as f:
            parser.write(f)

    @classmethod
    def read_cli_setting(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        parser = cls._read_parser()
        if not parser.has_section(CLI_SECTION):
            return default
        value = parser[CLI_SECTION].get(key, "").strip()
        return value or default

    @classmethod
    def write_cli_setting(cls, key: str, value: Optional[str]) -> None:
        """Set one CLI setting; None removes it."""
        parser = cls._read_parser()
        if not parser.has_section(CLI_SECTION):
            parser.add_section(CLI_SECTION)
        if value is None:
            parser.remove_option(CLI_SECTION, key)
        else:
            parser[CLI_SECTION][key] = value
        cls._write_parser(parser)

    @classmethod
    def current_api_name(cls) -> str:
        """The API the CLI points at: $ARCSECOND_API, else the recorded
        pointer, else 'cloud'."""
        override = os.environ.get(API_NAME_ENV_VAR, "").strip()
        if override:
            return override
        return cls.read_cli_setting(CLI_KEY_API) or DEFAULT_API_NAME

    @classmethod
    def is_api_name_overridden(cls) -> bool:
        return bool(os.environ.get(API_NAME_ENV_VAR, "").strip())

    @classmethod
    def set_current_api_name(cls, name: str) -> None:
        if name not in cls.registered_api_names():
            raise ArcsecondError(
                f"No API server is registered under the name '{name}'. "
                "Register it first:  arcsecond api add <name> <address>"
            )
        cls.write_cli_setting(CLI_KEY_API, name)

    @classmethod
    def registered_api_names(cls) -> list:
        """'cloud' first, then every section that carries a server address."""
        parser = cls._read_parser()
        names = [DEFAULT_API_NAME]
        for section_name in parser.sections():
            if section_name in (CLI_SECTION, DEFAULT_API_NAME):
                continue
            if parser[section_name].get("api_server", "").strip():
                names.append(section_name)
        return names

    @classmethod
    def remove_api(cls, name: str) -> None:
        """Forget a registered server, credentials included. The pointer falls
        back to 'cloud' if it was aimed at the removed one."""
        if name == DEFAULT_API_NAME:
            raise ArcsecondError("The 'cloud' API server cannot be removed.")
        parser = cls._read_parser()
        if (
            not parser.has_section(name)
            or not parser[name].get("api_server", "").strip()
        ):
            raise ArcsecondError(
                f"No API server is registered under the name '{name}'."
            )
        parser.remove_section(name)
        if (
            parser.has_section(CLI_SECTION)
            and parser[CLI_SECTION].get(CLI_KEY_API) == name
        ):
            parser.remove_option(CLI_SECTION, CLI_KEY_API)
        cls._write_parser(parser)

    @classmethod
    def __old_config_file_path(cls):
        return (Path.home() / ".arcsecond.ini").expanduser()

    @classmethod
    def is_dir_path_overridden(cls) -> bool:
        return bool(os.environ.get(CONFIG_DIR_ENV_VAR, "").strip())

    @classmethod
    def dir_path(cls) -> Path:
        """The directory holding config.ini and everything beside it.

        ``$ARCSECOND_CONFIG_DIR`` wins when it is set; otherwise the usual
        ``~/.config/arcsecond``.
        """
        override = os.environ.get(CONFIG_DIR_ENV_VAR, "").strip()
        if override:
            return Path(override).expanduser()
        return Path.home() / ".config" / "arcsecond"

    @classmethod
    def file_path(cls) -> Path:
        _config_dir_path = ArcsecondConfig.dir_path()
        _config_file_path = _config_dir_path / "config.ini"

        # The one-time move of the pre-0.9 ~/.arcsecond.ini happens only for
        # the real config directory. Doing it for an overridden one would take
        # the file out of the operator's home and drop it somewhere temporary —
        # which, during a test run, would destroy it.
        if (
            not ArcsecondConfig.is_dir_path_overridden()
            and ArcsecondConfig.__old_config_file_path().exists()
            and not _config_file_path.exists()
        ):
            _config_dir_path.mkdir(parents=True, exist_ok=True)
            shutil.move(
                str(ArcsecondConfig.__old_config_file_path()), str(_config_file_path)
            )
        elif not _config_file_path.exists():
            _config_file_path.parents[0].mkdir(parents=True, exist_ok=True)
            _config_file_path.touch()
        return _config_file_path

    @property
    def is_logged_in(self) -> bool:
        if self.__section is None:
            return False
        return (
            self.__section.get("access_key") is not None
            or self.__section.get("upload_key") is not None
        )

    def __save(self) -> None:
        with open(ArcsecondConfig.file_path(), "w") as f:
            self.__config.write(f)

    def reset(self) -> None:
        if self.__section is not None:
            del self.__config[self.api_name]
            self.__section = None
        self.__save()

    def __read_key(self, key: str) -> str:
        return self.__section.get(key, "") if self.__section else ""

    @property
    def verbose(self) -> int:
        return self.__verbose

    @property
    def api_name(self) -> Optional[str]:
        result = self.__api_name
        if not result:
            result = "cloud"
        return result

    @property
    def all_apis(self) -> Optional[str]:
        """One line per registered server, the current one marked with '*'."""
        current = ArcsecondConfig.current_api_name()

        def line(name, address, note=""):
            mark = "*" if name == current else " "
            return f" {mark} {name}: {address}{note}"

        apis = [line(DEFAULT_API_NAME, ARCSECOND_API_URL_PROD, " (protected)")]
        for section_name in self.__config.sections():
            if section_name in (CLI_SECTION, DEFAULT_API_NAME):
                continue
            api_server = self.__config[section_name].get("api_server", "")
            if api_server:
                apis.append(line(section_name, api_server))
        return "\n".join(apis)

    @property
    def api_server(self) -> Optional[str]:
        result = self.__read_key("api_server")
        if self.api_name == "cloud" and (result is None or result == ""):
            result = ARCSECOND_API_URL_PROD
        return result

    @api_server.setter
    def api_server(self, value) -> None:
        if self.api_name == "cloud":
            raise ArcsecondError("You cannot override the master cloud server address.")
        self.__section["api_server"] = value
        self.__save()

    @property
    def username(self) -> str:
        return self.__read_key("username")

    @property
    def access_key(self) -> str:
        return self.__read_key("access_key") or self.__read_key("api_key")

    @property
    def upload_key(self) -> str:
        return self.__read_key("upload_key")

    def read_key(self, key_name: str) -> str:
        return self.__section[key_name] if key_name in self.__section else None

    def clear_access_key(self) -> None:
        return self.__clear_key("access_key")

    def clear_upload_key(self) -> None:
        return self.__clear_key("upload_key")

    def __clear_key(self, key_name: str) -> None:
        if key_name in self.__section.keys():
            del self.__section[key_name]
            self.__save()

    def save(self, **kwargs) -> None:
        for k, v in kwargs.items():
            self.__section[k] = v
        self.__save()

    @property
    def memberships(self):
        results = {}
        for k, v in self.__section.items():
            if k.startswith("membership__"):
                results[k.split("membership__")[-1]] = v
        return results

    def save_memberships(self, memberships: list) -> None:
        for membership in memberships:
            key = membership.get("organisation")
            if isinstance(key, dict):
                key = key.get("subdomain")
            value = membership.get("role")
            self.save(**{"membership__" + key: value})

    def save_access_key(self, access_key: str) -> None:
        self.save(access_key=access_key)

    def save_upload_key(self, upload_key: str) -> None:
        self.save(upload_key=upload_key)

    def save_shared_key(self, shared_key: str, subdomain: str) -> None:
        self.__section["shared:" + subdomain] = shared_key
