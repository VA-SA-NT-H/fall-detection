import unittest
from app.core.auth import get_password_hash, verify_password, create_access_token

class TestAuth(unittest.TestCase):
    def test_password_hashing(self):
        pw = "my-secure-password"
        hashed = get_password_hash(pw)
        self.assertNotEqual(pw, hashed)
        self.assertTrue(verify_password(pw, hashed))
        self.assertFalse(verify_password("wrong-pw", hashed))

    def test_jwt_generation(self):
        token = create_access_token(data={"sub": "admin"})
        self.assertIsNotNone(token)
        self.assertTrue(isinstance(token, str))

if __name__ == '__main__':
    unittest.main()
