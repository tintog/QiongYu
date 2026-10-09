"""Persistent local accounts, expiring sessions and administrative audit trail."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(os.environ.get('QIONGYU_AUTH_ROOT', Path(__file__).resolve().parents[2] / 'managed_data' / 'auth'))

@contextmanager
def db():
    ROOT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ROOT / 'accounts.sqlite3', timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, enabled INTEGER DEFAULT 1, created REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT, expires REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, username TEXT, action TEXT, target TEXT, created REAL)')
    if not con.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        for name, role, password in [('admin','admin',os.environ.get('QIONGYU_ADMIN_PASSWORD','Admin@2026')), ('user','user',os.environ.get('QIONGYU_USER_PASSWORD','User@2026'))]:
            con.execute('INSERT INTO users VALUES (?,?,?,?,?)',(name,encode(password),role,1,time.time()))
        con.commit()
    try:
        with con:
            yield con
    finally:
        con.close()

def encode(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),240000).hex()
    return salt + ':' + digest

def verify(password, stored):
    salt, digest = stored.split(':')
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),240000).hex(),digest)

def public(row):
    return {k:row[k] for k in ('username','role','enabled','created')}

def login(username, password, role):
    with db() as con:
        row=con.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not row or not row['enabled'] or row['role']!=role or not verify(password,row['password']):
            raise ValueError('账号、密码或所选角色不正确，或账户已停用')
        token=secrets.token_urlsafe(32)
        con.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        con.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),username,time.time()+8*3600))
    audit(username,'登录',role)
    return token,public(row)

def current(token):
    if not token:return None
    with db() as con:
        row=con.execute('SELECT u.* FROM users u JOIN sessions s ON s.username=u.username WHERE s.token=? AND s.expires>? AND u.enabled=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
    return public(row) if row else None

def logout(token):
    with db() as con:con.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))

def audit(username, action, target=''):
    with db() as con:con.execute('INSERT INTO audit(username,action,target,created) VALUES(?,?,?,?)',(username,action,target,time.time()))

def users():
    with db() as con:return [public(r) for r in con.execute('SELECT * FROM users ORDER BY created')]

def save_user(username, role, enabled, password=None, create=False):
    if role not in ('user','admin'):raise ValueError('无效角色')
    if not username.strip() or len(username)>64:raise ValueError('账号长度应为1—64字符')
    if password is not None and not 8<=len(password)<=128:raise ValueError('密码长度应为8—128字符')
    with db() as con:
        old=con.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if create:
            if old:raise ValueError('账号已存在')
            if password is None:raise ValueError('请设置初始密码')
            con.execute('INSERT INTO users VALUES(?,?,?,?,?)',(username,encode(password),role,int(enabled),time.time()))
        else:
            if not old:raise ValueError('账号不存在')
            count=con.execute("SELECT count(*) FROM users WHERE role='admin' AND enabled=1").fetchone()[0]
            if old['role']=='admin' and old['enabled'] and (role!='admin' or not enabled) and count<=1:raise ValueError('不能停用或降级最后一个有效管理员')
            con.execute('UPDATE users SET role=?,enabled=?,password=? WHERE username=?',(role,int(enabled),encode(password) if password else old['password'],username))
            con.execute('DELETE FROM sessions WHERE username=?',(username,))
    return {'username':username,'role':role,'enabled':enabled}

def logs():
    with db() as con:return [dict(r) for r in con.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')]
