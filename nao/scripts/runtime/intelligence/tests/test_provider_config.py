import json

import pytest

try:
    from nao.scripts.runtime.intelligence.provider_config import (
        ProviderConfigBroadcaster,
        ProviderConfigError,
        ProviderConfigStore,
    )
except ImportError:
    ProviderConfigBroadcaster = None
    ProviderConfigError = ValueError
    ProviderConfigStore = None


def store(path, now_ms=lambda: 1234):
    assert ProviderConfigStore is not None, "provider config store is missing"
    return ProviderConfigStore(str(path), now_ms=now_ms)


def test_missing_or_malformed_file_falls_back_to_nonsecret_nemotron_selection(tmp_path):
    config = store(tmp_path / "provider.json")
    assert config.load() == {
        "selected": "nemotron", "active": "", "healthy": False,
        "error": "", "selection_version": 0, "updated_at_ms": 0,
    }

    (tmp_path / "provider.json").write_text('{"selected":"other","api_key":"leak"}')
    assert config.load()["selected"] == "nemotron"
    assert "api_key" not in config.load()


def test_selected_provider_is_allowlisted_and_saved_atomically(tmp_path):
    config = store(tmp_path / "provider.json")

    result = config.save_selected("gemma_local")

    assert result["selected"] == "gemma_local"
    assert result["selection_version"] == 1
    assert result["active"] == ""
    assert json.loads((tmp_path / "provider.json").read_text())["selected"] == "gemma_local"
    assert not (tmp_path / "provider.json.tmp").exists()

    with pytest.raises(ProviderConfigError, match="unsupported"):
        config.save_selected("http://attacker.test")


def test_pc_status_update_preserves_selection_and_bounds_error(tmp_path):
    config = store(tmp_path / "provider.json")
    config.save_selected("gemma_local")

    result = config.save_status({
        "active": "nemotron", "healthy": True, "error": "",
    })

    assert result == {
        "selected": "gemma_local", "active": "nemotron", "healthy": True,
        "error": "", "selection_version": 1, "updated_at_ms": 1234,
    }
    with pytest.raises(ProviderConfigError, match="invalid"):
        config.save_status({"active": "nemotron", "healthy": False, "error": "x" * 201})


def test_broadcaster_sends_only_allowlisted_selection_when_file_changes(tmp_path):
    assert ProviderConfigBroadcaster is not None, "provider broadcaster is missing"
    config = store(tmp_path / "provider.json")
    sent = []
    broadcaster = ProviderConfigBroadcaster(
        config, lambda kind, payload: sent.append((kind, payload))
    )

    broadcaster.sync(force=True)
    broadcaster.sync()
    config.save_selected("gemma_local")
    broadcaster.sync()
    config.save_selected("gemma_local")
    broadcaster.sync()

    assert sent == [
        ("provider_config", {"selected": "nemotron"}),
        ("provider_config", {"selected": "gemma_local"}),
        ("provider_config", {"selected": "gemma_local"}),
    ]
