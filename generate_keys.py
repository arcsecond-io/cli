#!/usr/bin/env python3

import base64
import os
import secrets

length = 50
chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'

secret_key = ''.join(secrets.choice(chars) for i in range(length))
print(f"SECRET_KEY={secret_key}")

new_key = base64.urlsafe_b64encode(os.urandom(32))
print(f"FIELD_ENCRYPTION_KEY={new_key.decode('UTF8')}")
