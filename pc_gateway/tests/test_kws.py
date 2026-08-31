from nao_gateway.kws import DetectionPolicy, KwsConfigurationError, KwsSettings


def test_detection_policy_requires_two_scores_and_applies_cooldown():
    policy = DetectionPolicy(0.995, cooldown_seconds=1.0)

    assert policy.update(0.996, 0.0) is False
    assert policy.update(0.998, 0.1) is True
    assert policy.update(0.998, 0.2) is False
    assert policy.update(0.998, 1.2) is True


def test_disabled_kws_does_not_require_model_artifacts():
    settings = KwsSettings.from_env({"NAO_KWS_ENABLED": "false"})

    assert settings.enabled is False


def test_blank_optional_paths_use_the_bundled_model_defaults():
    settings = KwsSettings.from_env({
        "NAO_KWS_ENABLED": "false", "NAO_KWS_MODEL_PATH": "",
        "NAO_KWS_ENCODER_PATH": "",
    })

    assert settings.model_path.name == "nao_classifier.onnx"
    assert settings.encoder_path.name == "openwakeword_encoder"


def test_enabled_kws_rejects_missing_model_assets(tmp_path):
    try:
        KwsSettings.from_env({
            "NAO_KWS_ENABLED": "true",
            "NAO_KWS_MODEL_PATH": str(tmp_path / "missing.onnx"),
        })
    except KwsConfigurationError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("KWS configuration should require the model artifacts")
