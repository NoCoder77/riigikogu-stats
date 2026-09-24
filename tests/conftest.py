"""Pytest fixtures and env for tests."""
import os

# Allow tests to run without a real DB; API tests will mock connect_db.
os.environ.setdefault("DATABASE_URL", "sqlite:///riigikogu_test.db")
