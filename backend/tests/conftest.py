import os


# Keep test collection and application startup away from the protected dev DB.
os.environ["DB_URL"] = "sqlite:///:memory:"
