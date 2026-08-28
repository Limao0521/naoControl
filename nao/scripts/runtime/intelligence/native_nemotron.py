#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Robot-local thin Nemotron client; all model computation remains in NVIDIA cloud."""
from __future__ import absolute_import, print_function

import base64
import json
import os
import re
import subprocess
import tempfile

try:
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 on NAO
    from urllib2 import Request, urlopen


DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_AGENT_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
DEFAULT_VISION_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_SECRET_PATH = "/home/nao/naoControl/config/nvidia_api_key"
DEFAULT_KNOWLEDGE_PATH = "/home/nao/naoControl/config/agent_knowledge.json"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_JPEG_BYTES = 2 * 1024 * 1024

try:
    STRING_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 tests
    STRING_TYPES = (str,)


class NativeRuntimeError(RuntimeError):
    pass


def fetch_latest_jpeg(url="http://127.0.0.1:8080/video.mjpeg", opener=urlopen):
    response = opener(url, timeout=5)
    data = bytearray()
    while len(data) <= MAX_JPEG_BYTES:
        chunk = response.read(4096)
        if not chunk:
            break
        data.extend(chunk)
        raw = bytes(data)
        start = raw.find(b"\xff\xd8")
        end = raw.find(b"\xff\xd9", start + 2) if start >= 0 else -1
        if start >= 0 and end >= 0:
            return raw[start:end + 2]
    raise NativeRuntimeError("NAO camera frame is unavailable")


class NativeCloudConfig(object):
    def __init__(self, secret_path=DEFAULT_SECRET_PATH, base_url=DEFAULT_BASE_URL,
                 agent_model=DEFAULT_AGENT_MODEL, vision_model=DEFAULT_VISION_MODEL):
        self.secret_path = secret_path
        self.base_url = base_url.rstrip("/")
        self.agent_model = agent_model
        self.vision_model = vision_model

    def __repr__(self):
        return "NativeCloudConfig(base_url={!r}, secret_path={!r})".format(
            self.base_url, self.secret_path
        )

    def api_key(self):
        try:
            with open(self.secret_path, "rb") as source:
                value = source.read(1025).strip()
        except (IOError, OSError):
            raise NativeRuntimeError("NVIDIA API key is not configured on the NAO")
        if not isinstance(value, str):
            value = value.decode("ascii")
        if len(value) < 20 or len(value) > 1024 or not re.match(r"^[A-Za-z0-9._-]+$", value):
            raise NativeRuntimeError("NVIDIA API key is invalid")
        return value

    def ready(self):
        try:
            self.api_key()
            return True
        except NativeRuntimeError:
            return False


class UrllibJsonTransport(object):
    """Preferred zero-dependency HTTPS transport from the robot Python runtime."""

    def __call__(self, url, headers, body, timeout):
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        if not isinstance(payload, bytes):
            payload = payload.encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers)
        try:
            response = urlopen(
                Request(url, data=payload, headers=request_headers), timeout=timeout
            )
            output = response.read(MAX_RESPONSE_BYTES + 1)
        except Exception as error:
            raise NativeRuntimeError(
                "NVIDIA HTTPS request failed: {}".format(type(error).__name__)
            )
        if len(output) > MAX_RESPONSE_BYTES:
            raise NativeRuntimeError("NVIDIA response is too large")
        try:
            result = json.loads(output.decode("utf-8"))
        except (TypeError, ValueError, UnicodeError):
            raise NativeRuntimeError("NVIDIA response is invalid")
        if not isinstance(result, dict):
            raise NativeRuntimeError("NVIDIA response is invalid")
        return result


class FallbackJsonTransport(object):
    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback

    def __call__(self, *args):
        try:
            return self.primary(*args)
        except NativeRuntimeError:
            if self.fallback is None:
                raise
            return self.fallback(*args)


class CurlJsonTransport(object):
    """Use curl so NAO's legacy Python SSL stack never handles cloud TLS."""
    def __init__(self, executable=None):
        self.executable = executable or os.environ.get("NAO_CONTROL_CURL", "/usr/bin/curl")

    def ready(self):
        return os.path.isfile(self.executable) and os.access(self.executable, os.X_OK)

    @staticmethod
    def _quoted(value):
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def __call__(self, url, headers, body, timeout):
        if not self.ready():
            raise NativeRuntimeError("modern curl runtime is not installed on the NAO")
        body_file = tempfile.NamedTemporaryFile(prefix="nao-nemotron-body-", delete=False)
        config_file = tempfile.NamedTemporaryFile(prefix="nao-nemotron-curl-", delete=False)
        try:
            payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            if not isinstance(payload, bytes):
                payload = payload.encode("utf-8")
            body_file.write(payload)
            body_file.close()
            os.chmod(body_file.name, 0o600)
            lines = [
                'url = "{}"'.format(self._quoted(url)),
                'request = "POST"',
                'silent', 'show-error', 'fail',
                'connect-timeout = 10', 'max-time = {}'.format(int(timeout)),
                'header = "Content-Type: application/json"',
            ]
            for name, value in headers.items():
                lines.append('header = "{}: {}"'.format(
                    self._quoted(name), self._quoted(value)
                ))
            lines.append('data-binary = "@{}"'.format(self._quoted(body_file.name)))
            encoded = ("\n".join(lines) + "\n").encode("utf-8")
            config_file.write(encoded)
            config_file.close()
            os.chmod(config_file.name, 0o600)
            process = subprocess.Popen(
                [self.executable, "--config", config_file.name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            output, error = process.communicate()
            if process.returncode != 0:
                message = error.decode("utf-8", "replace")[:300]
                raise NativeRuntimeError("NVIDIA request failed: " + message)
            if len(output) > MAX_RESPONSE_BYTES:
                raise NativeRuntimeError("NVIDIA response is too large")
            try:
                result = json.loads(output.decode("utf-8"))
            except (TypeError, ValueError, UnicodeError):
                raise NativeRuntimeError("NVIDIA response is invalid")
            if not isinstance(result, dict):
                raise NativeRuntimeError("NVIDIA response is invalid")
            return result
        finally:
            for handle in (body_file, config_file):
                try:
                    handle.close()
                except Exception:
                    pass
                try:
                    os.remove(handle.name)
                except OSError:
                    pass


def _message(response):
    try:
        return response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise NativeRuntimeError("NVIDIA completion is invalid")


def _json_object(text):
    if not isinstance(text, STRING_TYPES):
        raise NativeRuntimeError("Nemotron response did not contain JSON")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise NativeRuntimeError("Nemotron response did not contain JSON")
    try:
        value = json.loads(text[start:end + 1])
    except (TypeError, ValueError):
        raise NativeRuntimeError("Nemotron response did not contain valid JSON")
    if not isinstance(value, dict):
        raise NativeRuntimeError("Nemotron response did not contain an object")
    return value


def _load_prompt(path, language):
    try:
        with open(path, "rb") as source:
            knowledge = json.loads(source.read().decode("utf-8"))
        facts = knowledge["facts"]
    except (IOError, OSError, KeyError, TypeError, ValueError, UnicodeError):
        raise NativeRuntimeError("agent knowledge base is invalid")
    if not facts or not all(isinstance(item, STRING_TYPES) for item in facts):
        raise NativeRuntimeError("agent knowledge base is invalid")
    language_rule = (
        "Responde solamente en español." if language == "es"
        else "Respond only in English."
    )
    return (
        "Eres NAO, robot y capitán robótico del equipo HSL de Sabana Herons. "
        "Tu personalidad es 80% compañero del semillero y 20% embajador: cercana, "
        "divulgativa, breve, competitiva y con humor muy ligero. Habla en primera "
        "persona, trata al usuario de tú y no digas que eres portavoz oficial. "
        + language_rule + " No inventes hechos. Si no sabes algo, dilo. No entregues "
        "información de admisiones, precios, matrículas, becas o trámites. No emitas "
        "opiniones políticas o religiosas. Puedes describir objetos o personas visibles "
        "sin identificarlas ni inferir atributos sensibles. Solo pide una acción física "
        "si el usuario la solicitó explícitamente; si es ambiguo, pregunta. Devuelve "
        "exclusivamente JSON con speech y tool_calls. Hechos curados:\n- "
        + "\n- ".join(facts)
    )


def _tool_parameters(name, constraints):
    if name == "set_posture":
        return {"type": "object", "properties": {
            "posture": {"type": "string", "enum": constraints.get("allowed", [])},
            "speed": {"type": "number", "minimum": 0,
                      "maximum": constraints.get("max_speed", 0.5)},
        }, "required": ["posture"], "additionalProperties": False}
    if name == "set_led":
        return {"type": "object", "properties": {
            "group": {"type": "string", "enum": constraints.get("groups", [])},
            "color": {"type": "string", "enum": constraints.get("colors", [])},
        }, "required": ["group", "color"], "additionalProperties": False}
    if name == "look":
        return {"type": "object", "properties": {
            "yaw": {"type": "number", "minimum": constraints.get("yaw_range", [-1.0, 1.0])[0],
                    "maximum": constraints.get("yaw_range", [-1.0, 1.0])[1]},
            "pitch": {"type": "number", "minimum": constraints.get("pitch_range", [-0.5, 0.5])[0],
                      "maximum": constraints.get("pitch_range", [-0.5, 0.5])[1]},
            "speed": {"type": "number", "minimum": 0,
                      "maximum": constraints.get("max_speed", 0.15)},
        }, "required": ["yaw", "pitch"], "additionalProperties": False}
    if name == "run_behavior":
        return {"type": "object", "properties": {
            "behavior_id": {"type": "string", "enum": constraints.get("allowed_behavior_ids", [])},
        }, "required": ["behavior_id"], "additionalProperties": False}
    return {"type": "object", "properties": {}, "additionalProperties": False}


class NativeNemotronClient(object):
    def __init__(self, config, transport=None, knowledge_path=DEFAULT_KNOWLEDGE_PATH):
        self.config = config
        if transport is None:
            curl = CurlJsonTransport()
            transport = FallbackJsonTransport(
                UrllibJsonTransport(), curl if curl.ready() else None
            )
        self.transport = transport
        self.knowledge_path = knowledge_path

    def _post(self, body, timeout=90):
        return self.transport(
            self.config.base_url + "/chat/completions",
            {"Authorization": "Bearer " + self.config.api_key()},
            body, timeout,
        )

    def perceive(self, audio_wav, image):
        content = [{"type": "audio_url", "audio_url": {"url":
            "data:audio/wav;base64," + base64.b64encode(audio_wav).decode("ascii")}}]
        if image:
            content.append({"type": "image_url", "image_url": {"url":
                "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")}})
        response = self._post({
            "model": self.config.vision_model,
            "messages": [
                {"role": "system", "content": "Transcribe fielmente el audio en el idioma hablado y describe solo evidencia visible. Devuelve JSON con transcript, scene_summary, objects y uncertainties."},
                {"role": "user", "content": content},
            ],
            "temperature": 0, "max_tokens": 512,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        })
        data = _json_object(_message(response).get("content", ""))
        for key in ("transcript", "scene_summary"):
            if not isinstance(data.get(key), STRING_TYPES):
                data[key] = ""
        for key in ("objects", "uncertainties"):
            if not isinstance(data.get(key), list):
                data[key] = []
        return data

    def decide(self, transcript, scene, tools, language="es"):
        native_tools = [{"type": "function", "function": {
            "name": item["name"],
            "description": "Ejecuta una acción NAO autorizada",
            "parameters": _tool_parameters(item["name"], item.get("constraints", {})),
        }} for item in tools]
        response = self._post({
            "model": self.config.agent_model,
            "messages": [
                {"role": "system", "content": _load_prompt(self.knowledge_path, language)},
                {"role": "user", "content": json.dumps({
                    "transcript": transcript, "visual_context": scene, "tools": tools,
                }, ensure_ascii=False)},
            ],
            "temperature": 0, "max_tokens": 180,
            "chat_template_kwargs": {"enable_thinking": False},
            "tools": native_tools, "tool_choice": "auto",
        })
        message = _message(response)
        calls = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except (TypeError, ValueError):
                arguments = {}
            if function.get("name") and isinstance(arguments, dict):
                calls.append({"name": function["name"], "arguments": arguments})
        if calls:
            return {"speech": message.get("content") or "", "tool_calls": calls}
        data = _json_object(message.get("content", ""))
        return {
            "speech": data.get("speech", "") if isinstance(data.get("speech", ""), STRING_TYPES) else "",
            "tool_calls": data.get("tool_calls", []) if isinstance(data.get("tool_calls", []), list) else [],
        }


def _normalized(text):
    value = text.lower()
    replacements = ((u"á", "a"), (u"é", "e"), (u"í", "i"),
                    (u"ó", "o"), (u"ú", "u"), (u"ñ", "n"))
    for original, replacement in replacements:
        value = value.replace(original, replacement)
    return value


def _explicit_action(name, arguments, transcript):
    text = _normalized(transcript)
    if re.search(r"\b(no|nunca|not|never|don't|do not)\b", text):
        return False
    if name == "set_posture":
        posture = arguments.get("posture")
        cues = {
            "Stand": ("parate", "levantate", "ponte de pie", "pongas de pie", "stand up"),
            "StandInit": ("parate", "levantate", "ponte de pie", "pongas de pie", "stand up"),
            "Sit": ("sientate", "toma asiento", "sit down"),
            "Crouch": ("agachate", "crouch"),
        }
        return any(cue in text for cue in cues.get(posture, ()))
    if name == "run_behavior":
        return any(cue in text for cue in (
            "saluda", "asiente", "niega", "piensa", "baila", "saxofon", "tai chi",
            "wave", "nod", "dance", "saxophone",
        ))
    if name == "look":
        return any(cue in text for cue in ("mira", "gira la cabeza", "look", "turn your head"))
    if name == "set_led":
        target = any(cue in text for cue in ("luz", "luces", "ojos", "pecho", "oidos", "led"))
        verb = any(cue in text for cue in (
            "pon", "cambia", "enciende", "apaga", "set ", "change", "turn ",
        ))
        return target and verb
    return False


class NativeAgent(object):
    def __init__(self, client, executor, registry, state_publisher,
                 image_provider, language_provider):
        self.client = client
        self.executor = executor
        self.registry = registry
        self.state_publisher = state_publisher
        self.image_provider = image_provider
        self.language_provider = language_provider

    def _tools(self):
        tools = []
        for name, rule in self.registry.get("actions", {}).items():
            if name in ("say", "stop_all") or not rule.get("enabled", True):
                continue
            constraints = dict(rule)
            if name == "run_behavior":
                constraints["allowed_behavior_ids"] = sorted(self.registry.get("behaviors", {}).keys())
            tools.append({"name": name, "constraints": constraints})
        return tools

    def handle_audio(self, payload):
        interaction_id = payload.get("interaction_id", "unknown")
        audio = base64.b64decode(payload.get("audio_b64", ""))
        try:
            image = self.image_provider()
        except Exception as error:
            print("GATEWAY native_vision_unavailable error={}: {}".format(
                type(error).__name__, str(error)[:160]
            ))
            image = None
        perception = self.client.perceive(audio, image)
        transcript = perception["transcript"]
        print("TRANSCRIPTION turn={} text={!r}".format(interaction_id, transcript or "(vacía)"))
        self.state_publisher({
            "interaction_id": interaction_id, "phase": "processing",
            "transcript": transcript, "response": "", "actions": [],
        })
        decision = self.client.decide(
            transcript, perception["scene_summary"], self._tools(), self.language_provider()
        )
        actions = []
        tool_count = 0
        body_count = 0
        for call in decision["tool_calls"]:
            if not isinstance(call, dict):
                continue
            name = call.get("name", "")
            arguments = call.get("arguments") or {}
            rule = self.registry.get("actions", {}).get(name)
            if rule is None or not rule.get("enabled", True):
                actions.append({"name": name, "status": "rejected",
                                "reason": "action_not_allowed"})
                continue
            if tool_count >= 3:
                actions.append({"name": name, "status": "rejected",
                                "reason": "turn_tool_budget_exceeded"})
                continue
            if rule.get("risk") == "body" and body_count >= 1:
                actions.append({"name": name, "status": "rejected",
                                "reason": "body_action_budget_exceeded"})
                continue
            if not _explicit_action(name, arguments, transcript):
                actions.append({"name": name, "status": "rejected",
                                "reason": "physical_action_not_explicitly_requested"})
                continue
            tool_count += 1
            if rule.get("risk") == "body":
                body_count += 1
            result = self.executor.execute({"action": name, "arguments": arguments})
            actions.append({"name": name, "status": result.get("status", "unknown"),
                            "reason": result.get("reason")})
        speech = decision.get("speech", "")[:500]
        if speech:
            self.executor.execute({"action": "say", "arguments": {"text": speech}})
        self.state_publisher({
            "interaction_id": interaction_id, "phase": "ready",
            "transcript": transcript, "response": speech, "actions": actions,
        })
        return {"transcript": transcript, "response": speech, "actions": actions}
