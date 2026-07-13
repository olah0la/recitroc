"""Clients for external services.

TEACHING NOTE — this layer is the app's "outbound edge", the mirror image
of app/api (the inbound edge). Endpoints never call httpx directly; they
depend on a service object. That buys us:
- one place for timeouts/retries/base-URLs,
- typed return values instead of raw JSON spread across endpoints,
- trivial testing: inject a fake service, no network, no mocking library.
"""
