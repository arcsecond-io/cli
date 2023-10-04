import os
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

from .constants import ARCSECOND_API_URL_PROD


class Config(object):
    def __init__(self, section: str = 'main'):
        self.__config = ConfigParser()
        self.__config.read(str(Config.__config_file_path()))
        self.__section_name = section
        self.__org_section_name = section + ':organisations'
        self.__section = self.__config[section] \
            if self.__section_name in self.__config.sections() \
            else None
        self.__org_section = self.__config[self.__org_section_name] \
            if self.__org_section_name in self.__config.sections() \
            else None
        self.__section_name = section

    @classmethod
    def __old_config_file_path(cls):
        return (Path.home() / '.arcsecond.ini').expanduser()

    @classmethod
    def __config_dir_path(cls):
        _config_root_path = Path.home() / '.config'
        if 'XDG_CONFIG_DIRS' in os.environ.keys():
            _config_root_path = Path(os.environ['XDG_CONFIG_DIRS'])
        return _config_root_path / 'arcsecond'

    @classmethod
    def __config_file_path(cls) -> Path:
        _config_root_path = Path.home() / '.config'
        if 'XDG_CONFIG_DIRS' in os.environ.keys():
            _config_root_path = Path(os.environ['XDG_CONFIG_DIRS'])
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
            del self.__config[self.__section_name]
            self.__section = None
        if self.__org_section is not None:
            del self.__config[self.__org_section_name]
            self.__org_section = None
        self.__save()

    def __read_key(self, key: str) -> Optional[str]:
        return self.__section.get(key, None) if self.__section else None

    @property
    def api_server(self) -> Optional[str]:
        result = self.__read_key('api_server')
        if self.__section_name == 'main' and (result is None or result == ''):
            result = ARCSECOND_API_URL_PROD
        return result

    @property
    def username(self) -> Optional[str]:
        return self.__read_key('username')

    @property
    def access_key(self) -> Optional[str]:
        return self.__read_key('access_key')

    @property
    def upload_key(self) -> Optional[str]:
        return self.__read_key('upload_key')

    def clear_api_key(self) -> None:
        return self.__clear_key('access_key')

    def clear_upload_key(self, ) -> None:
        return self.__clear_key('upload_key')

    def __clear_key(self, key_name: str) -> None:
        if key_name in self.__section.keys():
            del self.__section[key_name]
            self.__save()

    def save(self, **kwargs) -> None:
        for k, v in kwargs.items():
            self.__section.set(k, v)
        self.__save()

    def save_api_key(self, access_key: str) -> None:
        self.save(access_key=access_key)

    def save_upload_key(self, upload_key: str) -> None:
        self.save(upload_key=upload_key)

    def save_shared_key(self, shared_key: str, username: str, organisation: str) -> None:
        self.__org_section.set(username=shared_key)
