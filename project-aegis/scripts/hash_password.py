"""Create a PBKDF2 password hash for AEGIS_USERS_JSON configuration."""
import getpass, hashlib, secrets
p=getpass.getpass('Password: '); salt=secrets.token_bytes(16); iterations=310000; digest=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,iterations).hex(); print(f'pbkdf2_sha256${iterations}${salt.hex()}${digest}')
