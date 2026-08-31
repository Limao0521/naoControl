"""Optional PC-microphone wake-word trigger for the NAO intelligent mode."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


logger = logging.getLogger(__name__)


class KwsConfigurationError(ValueError):
    pass


@dataclass
class DetectionPolicy:
    threshold: float
    required_hits: int = 2
    cooldown_seconds: float = 1.0
    _hits: int = field(default=0, init=False)
    _last_event: float = field(default=float("-inf"), init=False)

    def update(self, score: float, timestamp: float) -> bool:
        self._hits = self._hits + 1 if score >= self.threshold else 0
        if self._hits < self.required_hits:
            return False
        if timestamp - self._last_event < self.cooldown_seconds:
            self._hits = 0
            return False
        self._last_event = timestamp
        self._hits = 0
        return True


@dataclass(frozen=True)
class KwsSettings:
    enabled: bool
    model_path: Path
    encoder_path: Path
    threshold: float = 0.995
    blocksize: int = 16000

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "KwsSettings":
        enabled = env.get("NAO_KWS_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on",
        }
        package_root = Path(__file__).resolve().parents[2]
        model_path = Path(env.get("NAO_KWS_MODEL_PATH") or (
            package_root / "models" / "kws" / "nao_classifier.onnx"
        ))
        encoder_path = Path(env.get("NAO_KWS_ENCODER_PATH") or (
            model_path.parent / "openwakeword_encoder"
        ))
        try:
            threshold = float(env.get("NAO_KWS_THRESHOLD", "0.995"))
            blocksize = int(env.get("NAO_KWS_BLOCKSIZE", "16000"))
        except ValueError as error:
            raise KwsConfigurationError("invalid KWS threshold or block size") from error
        if not 0.0 < threshold <= 1.0 or blocksize < 1280 or blocksize > 32000:
            raise KwsConfigurationError("unsafe KWS threshold or block size")
        if enabled and (not model_path.is_file() or not encoder_path.is_dir()):
            raise KwsConfigurationError("KWS model or encoder assets are missing")
        return cls(enabled, model_path, encoder_path, threshold, blocksize)


class WakeWordDetector:
    """Runs model inference in the PC audio callback and signals the NAO safely."""

    def __init__(self, settings: KwsSettings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.stream = None
        self._loop = None
        self._notify = None
        self._extractor = None
        self._session = None
        self._policy = DetectionPolicy(settings.threshold)

    def _load_runtime(self):
        try:
            import numpy as np
            import onnxruntime as ort
            import sounddevice as sd
            from openwakeword.utils import AudioFeatures
        except ImportError as error:
            raise KwsConfigurationError(
                "KWS dependencies are not installed; rerun setup-nemotron-pc-host.ps1"
            ) from error
        melspec = self.settings.encoder_path / "melspectrogram.onnx"
        embedding = self.settings.encoder_path / "embedding_model.onnx"
        if not melspec.is_file() or not embedding.is_file():
            raise KwsConfigurationError("KWS encoder files are incomplete")
        self._extractor = AudioFeatures(str(melspec), str(embedding), device="cpu")
        self._session = ort.InferenceSession(str(self.settings.model_path))
        return np, sd

    async def start(self, notify):
        if not self.settings.enabled or self.stream is not None:
            return False
        np, sd = self._load_runtime()
        self._loop = asyncio.get_running_loop()
        self._notify = notify

        def callback(indata, frames, callback_time, status):
            if status:
                logger.warning("KWS audio status: %s", status)
            try:
                pcm = (indata[:, 0] * 32767).astype(np.int16)
                features = self._extractor.embed_clips(pcm.reshape(1, -1))[:, -16:]
                score = float(self._session.run(None, {"features": features.astype(np.float32)})[0][0, 0])
                logger.info("KWS score=%.3f", score)
                if self._policy.update(score, self.clock()):
                    future = asyncio.run_coroutine_threadsafe(self._notify(), self._loop)
                    future.add_done_callback(self._log_notification_result)
                    logger.info("KWS keyword_detected")
            except Exception as error:
                logger.warning("KWS inference failed: %s: %s", type(error).__name__, error)

        self.stream = sd.InputStream(
            channels=1, samplerate=16000, blocksize=self.settings.blocksize,
            callback=callback,
        )
        self.stream.start()
        logger.info("KWS enabled threshold=%.3f blocksize=%s", self.settings.threshold, self.settings.blocksize)
        return True

    def _log_notification_result(self, future):
        try:
            future.result()
        except Exception as error:
            logger.warning("KWS robot notification failed: %s: %s", type(error).__name__, error)

    async def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
