import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

from arcsecond.options import State
from .constants import ARCSECOND_API_URL_PROD


class ArcsecondConfig(object):
    def __init__(self, state: State = None):
        self.__state = state or State()
        self.__config = ConfigParser()
        self.__config.read(str(ArcsecondConfig.file_path()))
        api_name = self.__state.api_name or 'main'
        if api_name not in self.__config.sections():
            self.__config.add_section(api_name)
        self.__section = self.__config[api_name]

    @classmethod
    def __old_config_file_path(cls):
        return (Path.home() / '.arcsecond.ini').expanduser()

    @classmethod
    def dir_path(cls):
        _config_root_path = Path.home() / '.config'
        return _config_root_path / 'arcsecond'

    @classmethod
    def file_path(cls) -> Path:
        _config_dir_path = ArcsecondConfig.dir_path()
        _config_file_path = _config_dir_path / 'config.ini'
        if ArcsecondConfig.__old_config_file_path().exists() and not _config_file_path.exists():
            _config_dir_path.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ArcsecondConfig.__old_config_file_path()), str(_config_file_path))
        elif not _config_file_path.exists():
            _config_file_path.parents[0].mkdir(parents=True, exist_ok=True)
            _config_file_path.touch()
        return _config_file_path

    @property
    def is_logged_in(self) -> bool:
        if self.__section is None:
            return False
        return self.__section.get('access_key') is not None or \
            self.__section.get('upload_key') is not None

    def __save(self) -> None:
        with open(ArcsecondConfig.file_path(), 'w') as f:
            self.__config.write(f)

    def reset(self) -> None:
        if self.__section is not None:
            del self.__config[self.api_name]
            self.__section = None
        self.__save()

    def __read_key(self, key: str) -> str:
        return self.__section.get(key, '') if self.__section else ''

    @property
    def verbose(self) -> Optional[bool]:
        return self.__state.verbose

    @property
    def is_using_cli(self) -> Optional[bool]:
        return self.__state.is_using_cli

    @property
    def api_name(self) -> Optional[str]:
        result = self.__state.api_name
        if not result:
            result = 'main'
        return result

    @property
    def api_server(self) -> Optional[str]:
        result = self.__read_key('api_server')
        if self.api_name == 'main' and (result is None or result == ''):
            result = ARCSECOND_API_URL_PROD
        return result

    @api_server.setter
    def api_server(self, value) -> None:
        self.__section['api_server'] = value
        self.__save()

    @property
    def username(self) -> str:
        return self.__read_key('username')

    @property
    def access_key(self) -> str:
        return self.__read_key('access_key') or self.__read_key('api_key')

    @property
    def upload_key(self) -> str:
        return self.__read_key('upload_key')

    def read_key(self, key_name: str) -> str:
        return self.__section[key_name] if key_name in self.__section else None

    def clear_access_key(self) -> None:
        return self.__clear_key('access_key')

    def clear_upload_key(self, ) -> None:
        return self.__clear_key('upload_key')

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
            if k.startswith('membership__'):
                results[k.split('membership__')[-1]] = v
        return results

    def save_memberships(self, memberships: list) -> None:
        for membership in memberships:
            key = membership.get('organisation')
            if isinstance(key, dict):
                key = key.get('subdomain')
            value = membership.get('role')
            self.save(**{'membership__' + key: value})

    def save_access_key(self, access_key: str) -> None:
        self.save(access_key=access_key)

    def save_upload_key(self, upload_key: str) -> None:
        self.save(upload_key=upload_key)

    def save_shared_key(self, shared_key: str, subdomain: str) -> None:
        self.__section['shared:' + subdomain] = shared_key
