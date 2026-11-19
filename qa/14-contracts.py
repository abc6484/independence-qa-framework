"""Reviewed contract snapshots are never auto-updated by a test run."""
import difflib
import json
from pathlib import Path
import yaml
from graphql import build_client_schema, get_introspection_query, print_schema
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from grpc_tools import protoc
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def same_contract(expected, actual, label):
    if expected != actual:
        diff = '\n'.join(difflib.unified_diff(str(expected).splitlines(), str(actual).splitlines(),
                                              fromfile='reviewed '+label, tofile='current '+label))
        raise AssertionError('Contract drift requires review.\n'+diff)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, indent=2)


def rest_contract(adapter):
    result = adapter.call('/openapi.json')
    assert result.status == 200
    baseline = yaml.safe_load((ROOT/'contracts/vampi.openapi.yaml').read_text())
    # Connexion rewrites only deployment URLs when serving its spec. They are not API shape.
    # Preserve server count and every other field; normalize just each server URL.
    for document in (baseline, result.data):
        for server in document.get('servers', []):
            server['url'] = '<deployment-url>'
    same_contract(canonical_json(baseline), canonical_json(result.data), 'OpenAPI')


def graphql_contract(adapter):
    result = adapter.call(get_introspection_query())
    assert result.status == 200 and not result.errors, result.errors
    current = print_schema(build_client_schema(result.data))+'\n'
    same_contract((ROOT/'contracts/dvga.graphql').read_text(), current, 'GraphQL SDL')


def proto_bytes(path):
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)/'descriptor.pb'
        code = protoc.main(['protoc', '-I'+str(path.parent), '--descriptor_set_out='+str(output),
                            '--include_imports', str(path)])
        assert code == 0, 'Proto compilation failed'
        return output.read_bytes()


def proto_contract(current):
    # Source descriptor check plus live RPC response tests. This server has no reflection.
    expected = proto_bytes(ROOT/'contracts/demo.proto')
    same_contract(expected, proto_bytes(current), 'protobuf descriptor')
