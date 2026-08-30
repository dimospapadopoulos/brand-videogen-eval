import pytest

from vgeval.providers import available, get_provider
from vgeval.providers.base import ImageToVideoProvider


def test_mock_is_registered():
    assert "mock" in available()


def test_get_provider_returns_instance():
    p = get_provider("mock")
    assert isinstance(p, ImageToVideoProvider)
    assert p.name == "mock"


def test_unknown_provider_raises():
    with pytest.raises(KeyError):
        get_provider("does-not-exist")
