import os
from configparser import ConfigParser


def config_file_path():
    return os.path.expanduser('~/.arcsecond.ini')


def config_file_exists():
    path = config_file_path()
    return os.path.exists(path) and os.path.isfile(path)


def config_file_is_valid(section='main'):
    if not config_file_exists():
        return False
    config = ConfigParser()
    config.read(config_file_path())
    return config[section].get('api_key')


def config_file_save_api_key(api_key, username, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.keys():
        config.add_section(section)
    config.set(section, 'username', username)
    config.set(section, 'api_key', api_key)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_save_organisation_membership(subdomain, role, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    section += ':organisations'
    if section not in config.keys():
        config.add_section(section)
    config.set(section, subdomain, role)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_read_organisation_memberships(section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    section += ':organisations'
    if section not in config.sections():
        return {}
    return config[section]


def config_file_read_key(key, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return None
    return config[section].get(key, None)


def config_file_read_api_key(section='main'):
    return config_file_read_key('api_key', section=section)


def config_file_read_username(section='main'):
    return config_file_read_key('username', section=section)


def config_file_clear_section(section):
    config = ConfigParser()
    config.read(config_file_path())
    if section in config.sections():
        del config[section]
    if section + ':organisations' in config.sections():
        del config[section + ':organisations']
    with open(config_file_path(), 'w') as f:
        config.write(f)
