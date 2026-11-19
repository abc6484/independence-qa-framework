"""Small protocol-neutral seam: adapters own transport, tests own domain assertions."""
from dataclasses import dataclass, field
from typing import Any, Protocol
import ipaddress
from urllib.parse import urlparse
import requests
import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from generated import demo_pb2, demo_pb2_grpc


def local_only(endpoint: str):
    host = urlparse(endpoint if '://' in endpoint else '//'+endpoint).hostname
    if host != 'localhost':
        try:
            assert ipaddress.ip_address(host).is_loopback
        except (ValueError, TypeError, AssertionError):
            raise ValueError('Lab targets must be literal loopback addresses or localhost') from None


@dataclass(frozen=True)
class Result:
    status: str | int
    data: Any
    errors: list = field(default_factory=list)


class Adapter(Protocol):
    def call(self, operation: str, payload: dict | None = None, **options) -> Result: ...
    def close(self): ...


class Rest:
    def __init__(self, endpoint):
        local_only(endpoint)
        self.endpoint = endpoint.rstrip('/')
        self.session = requests.Session()
        self.session.trust_env = False

    def call(self, operation, payload=None, *, method='GET', token=None):
        if not operation.startswith('/') or operation.startswith('//'):
            raise ValueError('Only relative lab paths are allowed')
        headers = {'Authorization': 'Bearer '+token} if token else {}
        r = self.session.request(method, self.endpoint+operation, json=payload,
                                 headers=headers, timeout=(2,5), allow_redirects=False)
        try:
            body = r.json()
        except requests.exceptions.JSONDecodeError:
            body = None
        return Result(r.status_code, body)

    def close(self):
        self.session.close()


class GraphQL(Rest):
    def call(self, operation, payload=None, *, token=None):
        # DVGA's me field takes its token as an argument, not a bearer header.
        r = super().call('/graphql', {'query':operation,'variables':payload or {}}, method='POST')
        body = r.data or {}
        return Result(r.status, body.get('data'), body.get('errors', []))


class CatalogGrpc:
    def __init__(self, endpoint):
        local_only(endpoint)
        self.channel = grpc.insecure_channel(endpoint)
        self.stub = demo_pb2_grpc.ProductCatalogServiceStub(self.channel)
        self.service = demo_pb2.DESCRIPTOR.services_by_name['ProductCatalogService']

    def call(self, operation, payload=None, **options):
        method = self.service.methods_by_name[operation]
        from google.protobuf.message_factory import GetMessageClass
        request = ParseDict(payload or {}, GetMessageClass(method.input_type)())
        try:
            response = getattr(self.stub, operation)(request, timeout=5)
            return Result('OK', MessageToDict(response, preserving_proto_field_name=True))
        except grpc.RpcError as exc:
            return Result(exc.code().name, None, [exc.details()])

    def close(self):
        self.channel.close()


FACTORIES = {'rest':Rest, 'graphql':GraphQL, 'grpc':CatalogGrpc}


def make_adapter(protocol, endpoint) -> Adapter:
    return FACTORIES[protocol](endpoint)
