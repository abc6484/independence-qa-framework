import pytest
from qa.adapters import local_only, make_adapter, Result, FACTORIES
from qa.contracts import same_contract, proto_bytes
from qa.contracts import ROOT

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('endpoint', ['https://example.com','http://10.0.0.1:80','http://127.0.0.1.example.com','8.8.8.8:3550','http://[::]:5000'])
def test_remote_targets_refused(endpoint):
    with pytest.raises(ValueError):
        local_only(endpoint)


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1:5102','localhost:3550','http://[::1]:5013'])
def test_loopback_allowed(endpoint):
    local_only(endpoint)


@pytest.mark.contract
@pytest.mark.parametrize('before,after', [('{"a":"string"}','{"a":"number"}'), ('type Query {a: String}','type Query {b: String}')])
def test_contract_mutation_is_caught(before, after):
    with pytest.raises(AssertionError, match='Contract drift'):
        same_contract(before, after, 'mutation-control')


@pytest.mark.contract
def test_proto_field_number_mutation_is_caught(tmp_path):
    original = ROOT/'contracts/demo.proto'
    changed = tmp_path/'demo.proto'
    changed.write_text(original.read_text().replace('string product_id = 1;', 'string product_id = 9;',1))
    with pytest.raises(AssertionError):
        same_contract(proto_bytes(original), proto_bytes(changed), 'protobuf')


def test_new_protocol_needs_no_core_change(monkeypatch):
    class Fake:
        def __init__(self, endpoint): pass
        def call(self, operation, payload=None, **options): return Result('OK', {'operation':operation})
        def close(self): pass
    monkeypatch.setitem(FACTORIES,'future',Fake)
    adapter = make_adapter('future','unused')
    assert adapter.call('ping').data == {'operation':'ping'}


def test_rest_redirect_style_path_refused():
    adapter = make_adapter('rest','http://127.0.0.1:1')
    try:
        with pytest.raises(ValueError): adapter.call('//example.com')
    finally:
        adapter.close()
