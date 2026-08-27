from app.services.password import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    assert hash_password("hunter2") != "hunter2"


def test_verify_roundtrip():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("hunter2")
    assert verify_password("wrong-password", hashed) is False


def test_hash_is_salted_differently_each_time():
    a = hash_password("hunter2")
    b = hash_password("hunter2")
    assert a != b
    assert verify_password("hunter2", a) is True
    assert verify_password("hunter2", b) is True
