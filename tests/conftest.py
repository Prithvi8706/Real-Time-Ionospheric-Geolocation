import pytest

import api.f107 as f107mod


@pytest.fixture(autouse=True)
def _no_real_omni_fetch(monkeypatch):
    """Keep the test suite offline: any unpatched F10.7 lookup fails fast."""
    monkeypatch.setattr(
        f107mod, "_fetch_year",
        lambda year: (_ for _ in ()).throw(OSError("network disabled in tests")),
    )
