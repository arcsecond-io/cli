import secrets


def generate_password():
    # No '%' to avoid interpolation surprises
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWZ0123456789!@#$^&*(-_=+)'
    return ''.join(secrets.choice(chars) for i in range(16))
