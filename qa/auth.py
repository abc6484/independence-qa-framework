"""Auth policies stay outside the shared transport seam."""
from uuid import uuid4


def lab_identity():
    suffix = uuid4().hex[:12]
    return {'username':'qa_'+suffix,'password':'FakeOnly_'+suffix,'email':suffix+'@example.invalid'}


def rest_account(adapter, **overrides):
    user = {**lab_identity(), **overrides}
    result = adapter.call('/users/v1/register', user, method='POST')
    assert result.status == 200 and result.data['status'] == 'success', result
    login = adapter.call('/users/v1/login', {k:user[k] for k in ('username','password')}, method='POST')
    assert login.status == 200 and login.data.get('auth_token'), login
    return user, login.data['auth_token']


def graphql_account(adapter):
    user = lab_identity()
    created = adapter.call('mutation($u:UserInput!){createUser(userData:$u){user{username}}}', {'u':user})
    assert created.status == 200 and not created.errors, created
    login = adapter.call('mutation($u:String!,$p:String!){login(username:$u,password:$p){accessToken}}',
                         {'u':user['username'],'p':user['password']})
    assert not login.errors and login.data['login']['accessToken'], login
    return user, login.data['login']['accessToken']
