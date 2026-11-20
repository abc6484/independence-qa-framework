import tempfile
from pathlib import Path
from qa.adapters import local_only, make_adapter, Result, FACTORIES
from qa.contracts import same_contract, proto_bytes, ROOT
from qa.runner import check, expect_error


@check('unit', cases=['https://example.com', 'http://10.0.0.1:80', 'http://127.0.0.1.example.com', '8.8.8.8:3550', 'http://[::]:5000'])
def test_remote_targets_refused(case):
    expect_error(ValueError, local_only, case)


@check('unit', cases=['http://127.0.0.1:5102', 'localhost:3550', 'http://[::1]:5013'])
def test_loopback_allowed(case):
    local_only(case)


@check('unit', 'contract', cases=[('{"a":"string"}', '{"a":"number"}'), ('type Query {a: String}', 'type Query {b: String}')])
def test_contract_mutation_is_caught(case):
    before, after = case
    expect_error(AssertionError, same_contract, before, after, 'mutation-control', match='Contract drift')


@check('unit', 'contract')
def test_proto_field_number_mutation_is_caught():
    original = ROOT / 'contracts/demo.proto'
    with tempfile.TemporaryDirectory() as tmp:
        changed = Path(tmp) / 'demo.proto'
        changed.write_text(original.read_text().replace('string product_id = 1;', 'string product_id = 9;', 1))
        expect_error(AssertionError, same_contract, proto_bytes(original), proto_bytes(changed), 'protobuf')


@check('unit')
def test_new_protocol_needs_no_core_change():
    class Fake:
        def __init__(self, endpoint): pass
        def call(self, operation, payload=None, **options): return Result('OK', {'operation': operation})
        def close(self): pass
    FACTORIES['future'] = Fake
    try:
        assert make_adapter('future', 'unused').call('ping').data == {'operation': 'ping'}
    finally:
        del FACTORIES['future']


@check('unit')
def test_rest_redirect_style_path_refused():
    adapter = make_adapter('rest', 'http://127.0.0.1:1')
    try:
        expect_error(ValueError, adapter.call, '//example.com')
    finally:
        adapter.close()
