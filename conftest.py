import os


# Apply before root-level tests import the application and its module-level app.
os.environ["DB_URL"] = "sqlite:///:memory:"

# This is an imperative smoke script that calls a live localhost server at import
# time; collecting it would mutate whichever database that server is using.
collect_ignore = ["test_agent.py"]


def pytest_collection_modifyitems(items):
    """Run stable fixture-based suites before legacy tests that reload app modules."""
    items.sort(key=lambda item: ("tongyong" not in item.nodeid, item.nodeid))
