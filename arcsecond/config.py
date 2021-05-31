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
    if section not in config.sections():
        return False
    return config[section].get('api_key') is not None or config[section].get('upload_key') is not None


def config_file_clear_section(section):
    config = ConfigParser()
    config.read(config_file_path())
    if section in config.sections():
        del config[section]
    if section + ':organisations' in config.sections():
        del config[section + ':organisations']
    with open(config_file_path(), 'w') as f:
        config.write(f)


# ------ Keys ------

def config_file_read_key(key, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return None
    return config[section].get(key, None)


def config_file_read_username(section='main'):
    return config_file_read_key('username', section=section)


def config_file_read_api_key(section='main'):
    return config_file_read_key('api_key', section=section)


def config_file_read_upload_key(section='main'):
    return config_file_read_key('upload_key', section=section)


def config_file_clear_api_key(section='main'):
    return __config_file_clear_key('api_key', section=section)


def config_file_clear_upload_key(section='main'):
    return __config_file_clear_key('upload_key', section=section)


def __config_file_clear_key(key_name, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.sections():
        return
    if key_name not in config[section].keys():
        return
    del config[section][key_name]
    with open(config_file_path(), 'w') as f:
        config.write(f)


def __config_file_save_personal_key(key_name, key_value, username, section='main'):
    config = ConfigParser()
    config.read(config_file_path())
    if section not in config.keys():
        config.add_section(section)
    config.set(section, 'username', username)
    config.set(section, key_name, key_value)
    with open(config_file_path(), 'w') as f:
        config.write(f)


def config_file_save_api_key(api_key, username, section='main'):
    __config_file_save_personal_key('api_key', api_key, username, section=section)


def config_file_save_upload_key(upload_key, username, section='main'):
    __config_file_save_personal_key('upload_key', upload_key, username, section=section)


def config_file_save_shared_key(shared_key, username, organisation, section='main'):
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
