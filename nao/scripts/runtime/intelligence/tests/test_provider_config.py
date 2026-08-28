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
        "error": "", "selection_version": 0, "language": "es",
        "language_version": 0, "gemma_base_url": "",
        "gemma_endpoint_version": 0, "updated_at_ms": 0,
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
        "error": "", "selection_version": 1, "language": "es",
        "language_version": 0, "gemma_base_url": "",
        "gemma_endpoint_version": 0, "updated_at_ms": 1234,
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
        ("provider_config", {"selected": "nemotron", "language": "es", "gemma_base_url": ""}),
        ("provider_config", {"selected": "gemma_local", "language": "es", "gemma_base_url": ""}),
        ("provider_config", {"selected": "gemma_local", "language": "es", "gemma_base_url": ""}),
    ]


def test_language_is_allowlisted_persisted_and_broadcast(tmp_path):
    config = store(tmp_path / "provider.json")
    sent = []
    broadcaster = ProviderConfigBroadcaster(
        config, lambda kind, payload: sent.append((kind, payload))
    )
    broadcaster.sync(force=True)

    result = config.save_language("en")
    assert result["language"] == "en"
    assert result["language_version"] == 1
    broadcaster.sync()
    assert sent[-1] == (
        "provider_config", {"selected": "nemotron", "language": "en", "gemma_base_url": ""}
    )

    with pytest.raises(ProviderConfigError, match="unsupported language"):
        config.save_language("French")


def test_private_gemma_endpoint_is_persisted_and_broadcast_without_a_secret(tmp_path):
    config = store(tmp_path / "provider.json")
    sent = []
    broadcaster = ProviderConfigBroadcaster(
        config, lambda kind, payload: sent.append((kind, payload))
    )

    result = config.save_gemma_base_url("http://192.168.23.1:8080/v1")
    broadcaster.sync(force=True)

    assert result["gemma_base_url"] == "http://192.168.23.1:8080/v1"
    assert result["gemma_endpoint_version"] == 1
    assert sent[-1] == ("provider_config", {
        "selected": "nemotron", "language": "es",
        "gemma_base_url": "http://192.168.23.1:8080/v1",
    })
    with pytest.raises(ProviderConfigError, match="invalid Gemma"):
        config.save_gemma_base_url("https://example.org/v1")


def test_legacy_provider_state_migrates_to_spanish_without_losing_selection(tmp_path):
    path = tmp_path / "provider.json"
    path.write_text(json.dumps({
        "selected": "gemma_local", "active": "nemotron", "healthy": True,
        "error": "", "selection_version": 2, "updated_at_ms": 123,
    }), encoding="utf-8")

    state = store(path).load()

    assert state["selected"] == "gemma_local"
    assert state["language"] == "es"
    assert state["language_version"] == 0
