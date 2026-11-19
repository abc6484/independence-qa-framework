"""Security oracles assert safe behavior. No xfail, inverted assertions or silent allowances."""
from uuid import uuid4
import base64
import json
import pytest
from qa.auth import rest_account, graphql_account

pytestmark = [pytest.mark.integration, pytest.mark.security, pytest.mark.risk_high]


def test_rest_cross_user_book_secret_denied(rest):
    _, owner = rest_account(rest)
    _, attacker = rest_account(rest)
    title = 'qa_bola_'+uuid4().hex
    created = rest.call('/books/v1', {'book_title':title,'secret':'synthetic-owner-only'},method='POST',token=owner)
    assert created.status == 200
    positive = rest.call('/books/v1/'+title, token=owner)
    assert positive.status == 200 and positive.data['secret'] == 'synthetic-owner-only'
    observed = rest.call('/books/v1/'+title,token=attacker)
    assert observed.status in (403,404), 'BUG-001: another account can read a private book secret'


def test_rest_registration_cannot_grant_admin(rest):
    _, token = rest_account(rest, admin=True)
    result = rest.call('/me',token=token)
    assert result.status == 200
    assert result.data['data']['admin'] is False, 'BUG-002: self-registration grants admin privileges'


def test_rest_debug_does_not_expose_passwords(rest):
    result = rest.call('/users/v1/_debug')
    if result.status == 200:
        assert isinstance(result.data, dict) and isinstance(result.data.get('users'), list)
        assert all('password' not in user for user in result.data['users']), 'BUG-003: anonymous debug response exposes passwords'
    else:
        assert result.status in (401,403,404), 'Unexpected debug-endpoint error is not evidence of protection'


def test_graphql_private_paste_not_anonymous(gql):
    title = 'qa_private_'+uuid4().hex
    created = gql.call('mutation($t:String!){createPaste(title:$t,content:"synthetic-private",public:false){paste{id}}}',{'t':title})
    assert not created.errors, created
    identifier = int(created.data['createPaste']['paste']['id'])
    try:
        result = gql.call('query($id:Int!){paste(id:$id){content public}}',{'id':identifier})
        assert result.status in (200,401,403)
        assert result.errors or not (result.data or {}).get('paste'), 'BUG-004: anonymous caller reads a private paste'
    finally:
        cleanup = gql.call('mutation($id:Int!){deletePaste(id:$id){result}}',{'id':identifier})
        assert not cleanup.errors


def test_graphql_tampered_identity_token_rejected(gql):
    user, token = graphql_account(gql)
    # Establish a valid control first. Modify only a synthetic account token's identity;
    # keep the old signature, proving signature verification is missing if accepted.
    valid = gql.call('query($t:String!){me(token:$t){username}}', {'t':token})
    assert not valid.errors and valid.data['me']['username'] == user['username']
    header, payload, signature = token.split('.')
    claims = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
    claims['identity'] = 'admin'  # seeded lab identity, not an external account
    changed = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    forged = '.'.join((header,changed,signature))
    result = gql.call('query($t:String!){me(token:$t){username}}', {'t':forged})
    assert result.errors or not (result.data or {}).get('me'), 'BUG-005: tampered token impersonates the seeded lab admin'
