import os
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

from arcsecond.options import State
from .constants import ARCSECOND_API_URL_PROD


class Config(object):
    def __init__(self, state: State):
        self.__state = state
        self.__config = ConfigParser()
        self.__config.read(str(Config.__config_file_path()))
        self.__section = self.__config[self.api_name] \
            if self.api_name in self.__config.sections() \
            else None

    @classmethod
    def __old_config_file_path(cls):
        return (Path.home() / '.arcsecond.ini').expanduser()

    @classmethod
    def __config_dir_path(cls):
        _config_root_path = Path.home() / '.config'
        return _config_root_path / 'arcsecond'

    @classmethod
    def __config_file_path(cls) -> Path:
        _config_dir_path = Config.__config_dir_path()
        _config_file_path = _config_dir_path / 'config.ini'
        if Config.__old_config_file_path().exists() and not _config_file_path.exists():
            _config_dir_path.mkdir(parents=True, exist_ok=True)
            shutil.move(str(Config.__old_config_file_path()), str(_config_file_path))
        return _config_file_path

    @classmethod
    def __config_file_exists(cls) -> bool:
        path = Config.__config_file_path()
        return path.exists() and path.is_file()

    @property
    def file_path(self) -> str:
        return str(Config.__config_file_path())

    @property
    def is_logged_in(self) -> bool:
        if self.__section is None:
            return False
        return self.__section.get('access_key') is not None or \
            self.__section.get('upload_key') is not None

    def __save(self) -> None:
        with open(Config.__config_file_path(), 'w') as f:
            self.__config.write(f)

    def clear(self) -> None:
        if self.__section is not None:
            del self.__config[self.api_name]
            self.__section = None
        self.__save()

    def __read_key(self, key: str) -> Optional[str]:
        return self.__section.get(key, None) if self.__section else None

    @property
    def api_name(self) -> Optional[str]:
        return self.__state.api_name

    @property
    def subdomain(self) -> Optional[str]:
        return self.__state.subdomain

    @property
    def verbose(self) -> Optional[str]:
        return self.__state.verbose

    @property
    def api_server(self) -> Optional[str]:
        result = self.__read_key('api_server')
        if self.api_name == 'main' and (result is None or result == ''):
            result = ARCSECOND_API_URL_PROD
        return result

    @property
    def username(self) -> Optional[str]:
        return self.__read_key('username')

    @property
    def access_key(self) -> Optional[str]:
        return self.__read_key('access_key') or self.__read_key('api_key')

    @property
    def upload_key(self) -> Optional[str]:
        return self.__read_key('upload_key')

    def read_key(self, key_name: str, section_name: str = '') -> Optional[str]:
        section = self.__config[section_name] if section_name else self.__section
        return section[key_name] if key_name in section else None

    def clear_access_key(self) -> None:
        return self.__clear_key('access_key')

    def clear_upload_key(self, ) -> None:
        return self.__clear_key('upload_key')

    def __clear_key(self, key_name: str) -> None:
        if key_name in self.__section.keys():
            del self.__section[key_name]
            self.__save()

    def save(self, **kwargs) -> None:
        section_name = kwargs.pop('section', '')
        section = self.__config[section_name] if section_name else self.__section
        for k, v in kwargs.items():
            section[k] = v
        self.__save()

    def save_access_key(self, access_key: str) -> None:
        self.save(access_key=access_key)

    def save_upload_key(self, upload_key: str) -> None:
        self.save(upload_key=upload_key)

    def save_shared_key(self, shared_key: str, subdomain: str) -> None:
        subdomain = subdomain or self.__state.subdomain
        self.__section['shared:' + subdomain] = shared_key
