"""tests/agent/test_prompts.py - 守护占位符不丢失。"""
from backend.agent import prompts


def test_classifier_prompt_has_required_placeholders():
    p = prompts.CLASSIFIER_PROMPT
    for ph in ("{history}", "{prev_intent}", "{context_source}"):
        assert ph in p


def test_extract_prompt_has_required_placeholders():
    for ph in ("{msg}", "{intent}"):
        assert ph in prompts.EXTRACT_PROMPT


def test_schema_evolve_prompt_has_required_placeholders():
    for ph in ("{user_request}", "{current_schema}"):
        assert ph in prompts.SCHEMA_EVOLVE_PROMPT


def test_propose_prompt_has_required_placeholders():
    for ph in ("{gaps}", "{user_request}"):
        assert ph in prompts.PROPOSE_PROMPT


def test_code_gen_prompt_has_required_placeholders():
    for ph in ("{schema}", "{intent}", "{user_request}", "{code_type}", "{error_feedback}"):
        assert ph in prompts.CODE_GEN_PROMPT


def test_presenter_rephrase_prompt_has_required_placeholders():
    for ph in ("{intent}", "{summary_json}"):
        assert ph in prompts.PRESENTER_REPHRASE_PROMPT
