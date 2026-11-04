import os

# Ensure local test servers and workers on 127.0.0.1/localhost are never intercepted
# by an environment proxy when running test suites.
for key in ("NO_PROXY", "no_proxy"):
    current = os.environ.get(key, "")
    additions = [entry for entry in ("127.0.0.1", "localhost", "::1") if entry not in current]
    if additions:
        os.environ[key] = f"{current},{','.join(additions)}".strip(",")
