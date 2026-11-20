"""Local account credentials and revocable login sessions in the workspace SQLite DB."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

COOKIE_NAME = 'debate_session'
REMEMBER_SECONDS = 30 * 24 * 60 * 60
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class AuthError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalized_email(value):
    value = value.strip().casefold()
    if len(value) > 254 or not EMAIL.fullmatch(value):
        raise AuthError('Enter a valid email address.', 422)
    return value


def hash_password(password):
    if not 8 <= len(password) <= 128:
        raise AuthError('Use a password between 8 and 128 characters.', 422)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=32768, r=8, p=1,
                            maxmem=64*1024*1024, dklen=64)
    return f'scrypt-v1${salt.hex()}${digest.hex()}'


def verify_password(password, encoded):
    try:
        if not 1 <= len(password) <= 128:
            return False
        version, salt, expected = encoded.split('$')
        if version != 'scrypt-v1' or len(salt) != 32 or len(expected) != 128:
            return False
        digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=32768,
                                r=8, p=1, maxmem=64*1024*1024, dklen=64)
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError, AttributeError):
        return False


class AuthStore:
    def __init__(self, path):
        self.path = path
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires_at REAL NOT NULL, created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS login_expiry ON login_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS auth_attempts (
                    attempt_key TEXT PRIMARY KEY, failures INTEGER NOT NULL, window_start REAL NOT NULL
                );
            ''')
        Path(self.path).chmod(0o600)

    @contextmanager
    def db(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            yield db

    @staticmethod
    def public_user(row):
        return {key: row[key] for key in ('id','name','email','created_at')}

    def setup_required(self):
        with self.db() as db:
            return db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0

    def register(self, name, email, password):
        name = name.strip()
        if not name or len(name) > 80:
            raise AuthError('Enter a display name up to 80 characters.', 422)
        email = normalized_email(email)
        encoded = hash_password(password)
        user = {'id': str(uuid4()), 'name': name, 'email': email,
                'created_at': datetime.now(timezone.utc).isoformat()}
        try:
            with self.db() as db:
                # Serialize first-account adoption, even when two registrations arrive together.
                db.execute('BEGIN IMMEDIATE')
                first = db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
                db.execute('INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)',
                           (user['id'],name,email,encoded,user['created_at']))
                if first:
                    db.execute('UPDATE sessions SET owner_id=? WHERE owner_id IS NULL', (user['id'],))
        except sqlite3.IntegrityError as error:
            raise AuthError('An account with this email already exists. Sign in instead.',409) from error
        return user

    def authenticate(self, email, password, client_key):
        email = normalized_email(email)
        now = time.time()
        keys = [hashlib.sha256(f'ip:{client_key}'.encode()).hexdigest(),
                hashlib.sha256(f'email:{email}'.encode()).hexdigest()]
        with self.db() as db:
            db.execute('DELETE FROM auth_attempts WHERE window_start < ?', (now-300,))
            for key in keys:
                row = db.execute('SELECT failures FROM auth_attempts WHERE attempt_key=?',(key,)).fetchone()
                if row and row['failures'] >= 5:
                    raise AuthError('Too many sign-in attempts. Try again in five minutes.',429)
            row = db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        # A missing account still performs one password derivation.
        dummy = 'scrypt-v1$' + '00'*16 + '$' + '00'*64
        valid = verify_password(password, row['password_hash'] if row else dummy)
        with self.db() as db:
            if not row or not valid:
                for key in keys:
                    db.execute('INSERT INTO auth_attempts VALUES(?,1,?) ON CONFLICT(attempt_key) DO UPDATE SET failures=failures+1', (key,now))
            else:
                db.executemany('DELETE FROM auth_attempts WHERE attempt_key=?', [(key,) for key in keys])
        if not row or not valid:
            raise AuthError('Email or password is incorrect.',401)
        return self.public_user(row)

    def issue_session(self, user_id, remember=True):
        token = secrets.token_urlsafe(32)
        now = time.time()
        lifetime = REMEMBER_SECONDS if remember else 24*60*60
        with self.db() as db:
            db.execute('DELETE FROM login_sessions WHERE expires_at <= ?', (now,))
            db.execute('INSERT INTO login_sessions VALUES(?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user_id, now+lifetime, now))
        return token

    def user_for_token(self, token):
        if not isinstance(token,str) or not 20 <= len(token) <= 100:
            return None
        with self.db() as db:
            row = db.execute('SELECT users.* FROM login_sessions JOIN users ON users.id=login_sessions.user_id WHERE token_hash=? AND expires_at>?',
                             (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return self.public_user(row) if row else None

    def revoke(self, token):
        if isinstance(token,str):
            with self.db() as db:
                db.execute('DELETE FROM login_sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
