"""Optional signed bearer authentication for operator endpoints."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, time
from typing import Any

def enabled()->bool: return os.getenv('AEGIS_AUTH_ENABLED','false').lower() in ('1','true','yes')
def _b64(data:bytes)->str: return base64.urlsafe_b64encode(data).decode().rstrip('=')
def verify_password(password:str, encoded:str)->bool:
    try:
        scheme,iterations,salt,digest=encoded.split('$',3)
        if scheme!='pbkdf2_sha256': return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations))
        return hmac.compare_digest(actual.hex(),digest)
    except Exception: return False
def login(username:str,password:str)->dict[str,Any]|None:
    try: users=json.loads(os.getenv('AEGIS_USERS_JSON','{}'))
    except Exception: return None
    entry=users.get(username)
    if not isinstance(entry,dict) or not verify_password(password,str(entry.get('password_hash',''))): return None
    role=entry.get('role','responder')
    if role not in ('admin','supervisor','responder'): return None
    secret=os.getenv('AEGIS_AUTH_SECRET','')
    if len(secret)<32: return None
    payload={'sub':username,'role':role,'exp':int(time.time())+43200}
    body=_b64(json.dumps(payload,separators=(',',':')).encode()); sig=_b64(hmac.new(secret.encode(),body.encode(),hashlib.sha256).digest())
    return {'access_token':f'{body}.{sig}','token_type':'bearer','expires_in':43200,'role':payload['role']}
def decode_token(token:str)->dict[str,Any]|None:
    try:
        body,sig=token.split('.',1); secret=os.getenv('AEGIS_AUTH_SECRET','')
        expected=_b64(hmac.new(secret.encode(),body.encode(),hashlib.sha256).digest())
        if len(secret)<32 or not hmac.compare_digest(sig,expected): return None
        payload=json.loads(base64.urlsafe_b64decode(body+'='*((4-len(body)%4)%4)))
        if payload.get('exp',0)<time.time(): return None
        return payload
    except Exception:return None
