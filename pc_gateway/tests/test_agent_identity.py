from pathlib import Path

import pytest

from nao_gateway.agent_identity import (
    AgentKnowledgeError,
    build_decision_system_prompt,
    load_knowledge_base,
)


KNOWLEDGE_PATH = Path("config/agent_knowledge.json")


def test_curated_knowledge_distinguishes_team_and_official_sources():
    knowledge = load_knowledge_base(KNOWLEDGE_PATH)

    assert knowledge["verified_at"] == "2026-08-27"
    assert {source["authority"] for source in knowledge["sources"]} == {
        "team", "official",
    }
    assert any("RoboCup Humanoid Soccer League" in fact for fact in knowledge["facts"])
    assert not any("matrícula" in fact.lower() for fact in knowledge["facts"])


def test_spanish_prompt_defines_nao_personality_knowledge_and_safety_contract():
    prompt = build_decision_system_prompt("es", KNOWLEDGE_PATH)

    assert "Soy NAO" in prompt
    assert "capitán robótico del equipo HSL" in prompt
    assert "80 % compañero" in prompt
    assert "dos a cuatro frases" in prompt
    assert "No soy un portavoz oficial" in prompt
    assert "admisiones" in prompt and "no respondo" in prompt
    assert "política" in prompt and "religión" in prompt
    assert "solo si el usuario la pidió explícitamente" in prompt
    assert "pregunta antes de actuar" in prompt
    assert "RoboCup Humanoid Soccer League" in prompt
    assert "Ingeniería Informática" in prompt
    assert len(prompt) < 14000


def test_english_mode_changes_response_language_without_changing_identity():
    prompt = build_decision_system_prompt("en", KNOWLEDGE_PATH)

    assert "Respond only in English" in prompt
    assert "My name is NAO" in prompt
    assert "robotic captain of the HSL team" in prompt
    assert "RoboCup Humanoid Soccer League" in prompt


def test_prompt_rejects_unsupported_language():
    with pytest.raises(AgentKnowledgeError, match="unsupported language"):
        build_decision_system_prompt("French", KNOWLEDGE_PATH)
