from pathlib import Path
from uuid import uuid4
from jsonschema import validate
from qa.runner import check, CONFIG
from qa.auth import rest_account, graphql_account
from qa.contracts import rest_contract, graphql_contract, proto_contract



@check('integration', 'contract', 'risk_high')
def test_rest_contract(rest):
    rest_contract(rest)


@check('integration', 'contract', 'risk_high')
def test_graphql_contract(gql):
    graphql_contract(gql)


@check('integration', 'contract', 'risk_high')
def test_grpc_contract():
    proto_contract(Path(CONFIG['source_root']) / 'boutique/protos/demo.proto')


@check('integration', 'risk_high')
def test_rest_login_and_me(rest):
    user, token = rest_account(rest)
    response = rest.call('/me', token=token)
    assert response.status == 200
    validate(response.data, {'type':'object','required':['status','data'],'properties':{
        'status':{'const':'success'},'data':{'type':'object','required':['username','email','admin'],
        'properties':{'username':{'const':user['username']},'email':{'const':user['email']},'admin':{'type':'boolean'}}}}})


@check('integration', 'risk_high')
def test_rest_book_lifecycle(rest):
    user, token = rest_account(rest)
    title = 'qa_'+uuid4().hex
    created = rest.call('/books/v1', {'book_title':title,'secret':'synthetic secret'},method='POST',token=token)
    assert created.status == 200 and created.data['status'] == 'success'
    read = rest.call('/books/v1/'+title, token=token)
    assert read.status == 200 and read.data == {'book_title':title,'secret':'synthetic secret','owner':user['username']}
    duplicate = rest.call('/books/v1', {'book_title':title,'secret':'synthetic secret'},method='POST',token=token)
    assert duplicate.status == 400


@check('integration', 'risk_high')
def test_rest_anonymous_book_denied(rest):
    response = rest.call('/books/v1/no-such-synthetic-book')
    assert response.status == 401


@check('integration', 'risk_medium')
def test_rest_invalid_book_body(rest):
    _, token = rest_account(rest)
    assert rest.call('/books/v1', {}, method='POST',token=token).status == 400


@check('integration', 'risk_high')
def test_graphql_login_and_me(gql):
    user, token = graphql_account(gql)
    response = gql.call('query($t:String!){me(token:$t){username}}', {'t':token})
    assert response.status == 200 and not response.errors
    assert response.data['me']['username'] == user['username']


@check('integration', 'risk_high')
def test_graphql_public_paste_roundtrip(gql):
    title = 'qa_'+uuid4().hex
    created = gql.call('mutation($t:String!){createPaste(title:$t,content:"synthetic body",public:true){paste{id title}}}', {'t':title})
    assert created.status == 200 and not created.errors, created
    paste = created.data['createPaste']['paste']
    try:
        read = gql.call('query($id:Int!){paste(id:$id){id title content public}}', {'id':int(paste['id'])})
        assert not read.errors and read.data['paste']['title'] == title
        assert read.data['paste']['content'] == 'synthetic body' and read.data['paste']['public'] is True
    finally:
        cleanup = gql.call('mutation($id:Int!){deletePaste(id:$id){result}}', {'id':int(paste['id'])})
        assert not cleanup.errors and cleanup.data['deletePaste']['result'] is True


@check('integration', 'risk_medium', cases=['{fieldThatDoesNotExist}', 'query($id:Int!){paste(id:$id){title}}'])
def test_graphql_rejects_invalid_operations(gql, case):
    response = gql.call(case)
    assert response.status in (200, 400) and response.errors


@check('integration', 'risk_high')
def test_catalog_read_and_search(catalog):
    listed = catalog.call('ListProducts')
    assert listed.status == 'OK' and len(listed.data['products']) > 0
    first = listed.data['products'][0]
    assert first['id'] and first['name']
    assert first['price_usd']['currency_code'] == 'USD'
    detail = catalog.call('GetProduct', {'id':first['id']})
    assert detail.status == 'OK' and detail.data == first
    search = catalog.call('SearchProducts', {'query':first['name'].upper()})
    assert search.status == 'OK' and first['id'] in {p['id'] for p in search.data['results']}


@check('integration', 'risk_medium', cases=['nonexistent-synthetic-id', ''])
def test_catalog_not_found(catalog, case):
    response = catalog.call('GetProduct', {'id': case})
    assert response.status == 'NOT_FOUND'



@check('integration', 'risk_medium')
def test_catalog_no_match(catalog):
    result = catalog.call('SearchProducts', {'query':'qa_no_match_'+uuid4().hex})
    assert result.status == 'OK' and result.data.get('results',[]) == []


@check('integration', 'security', 'risk_medium')
def test_catalog_anonymous_read_is_intended(catalog):
    # No inter-service auth is part of this lab's stated architecture, not an invented bug.
    assert catalog.call('ListProducts').status == 'OK'
