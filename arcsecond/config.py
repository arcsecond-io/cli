import os
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

from .api.constants import ARCSECOND_API_URL_PROD


def old_config_file_path() -> Path:
    return (Path.home() / '.arcsecond.ini').expanduser()


def config_dir_path() -> Path:
    _config_root_path = Path.home() / '.config'
    if 'XDG_CONFIG_DIRS' in os.environ.keys():
        _config_root_path = Path(os.environ['XDG_CONFIG_DIRS'])
    return _config_root_path / 'arcsecond'


def config_file_path() -> Path:
    _config_dir_path = config_dir_path()
    _config_file_path = _config_dir_path / 'config.ini'
    if not _config_file_path.exists():
        _config_dir_path.mkdir(parents=True, exist_ok=True)
        if old_config_file_path().exists():
            shutil.move(str(old_config_file_path()), str(_config_file_path))
    return _config_file_path


def config_file_exists() -> bool:
    path = config_file_path()
    return os.path.exists(path) and os.path.isfile(path)


def config_file_is_logged_in(section: str = 'main') -> bool:
    if not config_file_exists():
        return False
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return False
    return config[section].get('api_key') is not None or config[section].get('upload_key') is not None


def config_file_clear_section(section: str = 'main') -> None:
    config = ConfigParser()
    config.read(config_file_path())
    if section in config.sections():
        del config[section]
    if section + ':organisations' in config.sections():
        del config[section + ':organisations']
    with open(config_file_path(), 'w') as f:
        config.write(f)


# ------ Keys ------

def config_file_read_key(key: str, section: str = 'main') -> Optional[str]:
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return None
    return config[section].get(key, None)


def config_file_read_api_server(section: str = 'main') -> Optional[str]:
    result = config_file_read_key('api_server', section=section)
    if section == 'main' and (result is None or result == ''):
        result = ARCSECOND_API_URL_PROD
    return result


def config_file_read_username(section: str = 'main') -> Optional[str]:
    return config_file_read_key('username', section=section)


def config_file_read_api_key(section: str = 'main') -> Optional[str]:
    return config_file_read_key('api_key', section=section)


def config_file_read_upload_key(section: str = 'main') -> Optional[str]:
    return config_file_read_key('upload_key', section=section)


def config_file_clear_api_key(section: str = 'main') -> Optional[str]:
    return _config_file_clear_key('api_key', section=section)


def config_file_clear_upload_key(section: str = 'main') -> Optional[str]:
    return _config_file_clear_key('upload_key', section=section)


def _config_file_clear_key(key_name: str, section: str = 'main') -> None:
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return
    if key_name not in config[section].keys():
        return
    del config[section][key_name]
    with open(config_file_path(), 'w') as f:
        config.write(f)


def _config_file_save_keys_values(**kwargs) -> None:
    section = kwargs.pop('section')
    if section is None:
        return
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.keys():
        config.add_section(section)
    for k, v in kwargs.items():
        config.set(section, k, v)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_save_username(username: str, section: str = 'main') -> None:
    _config_file_save_keys_values(username=username, section=section)


def config_file_save_api_server(address: str, section: str = 'main'):
    _config_file_save_keys_values(api_server=address, section=section)


def config_file_save_api_key(api_key: str, username: str, section: str = 'main') -> None:
    _config_file_save_keys_values(api_key=api_key, username=username, section=section)


def config_file_save_upload_key(upload_key: str, username: str, section: str = 'main') -> None:
    _config_file_save_keys_values(upload_key=upload_key, username=username, section=section)


def config_file_save_shared_key(shared_key: str, username: str, organisation: str, section: str = 'main') -> None:
    _config_file_save_keys_values(username=username, section=section)
    _config_file_save_keys_values(**{organisation: shared_key, 'section': section + ':uploads'})


# -------- ORGANISATIONS ----------------

def config_file_save_organisation_membership(subdomain: str, role: str, section: str = 'main') -> None:
    _config_file_save_keys_values(**{subdomain: role, 'section': section + ':organisations'})


def config_file_read_organisation_memberships(section: str = 'main') -> dict:
    config = ConfigParser()
    config.read(config_file_path())
    section += ':organisations'
    if section not in config.sections():
        return {}
    return dict(config[section])
