import pytest

from app import snmp_service


class FakeErrorStatus:
    def prettyPrint(self):
        return "authorizationError"


@pytest.mark.parametrize(
    ("error_indication", "error_status", "message"),
    [
        ("No SNMP response received before timeout", None, "timeout"),
        (None, FakeErrorStatus(), "authorizationError"),
    ],
)
def test_discovery_reports_snmp_walk_errors(
    monkeypatch, error_indication, error_status, message
):
    async def bulk_walk_cmd(*args, **kwargs):
        yield error_indication, error_status, 0, []

    class Target:
        @staticmethod
        async def create(*args, **kwargs):
            return object()

    monkeypatch.setattr(
        snmp_service,
        "_hlapi",
        lambda: {
            "SnmpEngine": object,
            "UsmUserData": lambda *args, **kwargs: object(),
            "UdpTransportTarget": Target,
            "ContextData": lambda *args, **kwargs: object(),
            "ObjectType": lambda value: value,
            "ObjectIdentity": lambda value: value,
            "bulk_walk_cmd": bulk_walk_cmd,
        },
    )

    with pytest.raises(RuntimeError, match=message):
        snmp_service.discover_neighbors({"host": "192.0.2.1", "username": "monitor"})
