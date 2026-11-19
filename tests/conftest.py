import os
import pytest
from qa.adapters import make_adapter


def pytest_addoption(parser):
    parser.addoption('--vampi-url', default='http://127.0.0.1:5102')
    parser.addoption('--dvga-url', default='http://127.0.0.1:5013')
    parser.addoption('--catalog-address', default='127.0.0.1:3550')
    parser.addoption('--source-root', default=os.environ.get('QA_SOURCE_ROOT', '.lab'))


@pytest.fixture
def rest(request):
    adapter = make_adapter('rest', request.config.getoption('--vampi-url'))
    yield adapter
    adapter.close()


@pytest.fixture
def gql(request):
    adapter = make_adapter('graphql', request.config.getoption('--dvga-url'))
    yield adapter
    adapter.close()


@pytest.fixture
def catalog(request):
    adapter = make_adapter('grpc', request.config.getoption('--catalog-address'))
    yield adapter
    adapter.close()
