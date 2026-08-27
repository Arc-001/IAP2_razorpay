"""Password hashing for login accounts. Uses bcrypt directly (not
passlib[bcrypt] — passlib's bcrypt backend has a known incompatibility with
bcrypt>=4.1's removed __about__ attribute, and we only need hash+verify, not
passlib's multi-scheme abstraction)."""

import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
