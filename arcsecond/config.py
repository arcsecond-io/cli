import os
from configparser import ConfigParser
from typing import Optional


def config_file_path() -> str:
    return os.path.expanduser('~/.arcsecond.ini')


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


def _config_file_save_personal_key(key_name: str, key_value: str, username: str, section: str = 'main') -> None:
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.keys():
        config.add_section(section)
    config.set(section, 'username', username)
    config.set(section, key_name, key_value)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_save_api_key(api_key: str, username: str, section: str = 'main') -> None:
    _config_file_save_personal_key('api_key', api_key, username, section=section)


def config_file_save_upload_key(upload_key: str, username: str, section: str = 'main') -> None:
    _config_file_save_personal_key('upload_key', upload_key, username, section=section)


def config_file_save_shared_key(shared_key: str, username: str, organisation: str, section: str = 'main') -> None:
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.keys():
        config.add_section(section)
    config.set(section, 'username', username)
    section += ':uploads'
    if section not in config.keys():
        config.add_section(section)
    config.set(section, organisation, shared_key)
    with open(config_file_path(), 'w') as f:
        config.write(f)


# -------- ORGANISATIONS ----------------

def config_file_save_organisation_membership(subdomain: str, role: str, section: str = 'main') -> None:
    config = ConfigParser()
    config.read(config_file_path())
    section += ':organisations'
    if section not in config.keys():
        config.add_section(section)
    config.set(section, subdomain, role)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_read_organisation_memberships(section: str = 'main') -> dict:
    config = ConfigParser()
    config.read(config_file_path())
    section += ':organisations'
    if section not in config.sections():
        return {}
    return dict(config[section])
