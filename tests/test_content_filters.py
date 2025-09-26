import importlib

import pytest

import system_prompt


def reload_module():
    return importlib.reload(system_prompt)


def test_ai_trace_sanitization_removes_common_phrases():
    module = reload_module()
    dirty = "As an AI language model, I cannot access the internet but I think it's fine."
    cleaned = module.sanitize_model_traces(dirty)
    assert "AI language model" not in cleaned
    assert "access the internet" not in cleaned
    assert cleaned.endswith("fine.")


def test_filter_rejects_financial_promises():
    module = reload_module()
    text = "Bu kesin kazanç fırsatı ile bedava para kazanırsın"
    assert module.filter_content(text) is None


@pytest.mark.parametrize(
    "input_text,expected_suffix",
    [
        ("Bu görüş kişisel fikrimdir; yatırım tavsiyesi değildir", "yatırım tavsiyesi değildir"),
        (
            "Bence bu hisse yükselebilir, yatırım tavsiyesi değil",
            "(Not: Yatırım tavsiyesi değildir.)",
        ),
    ],
)
def test_filter_appends_disclaimer_when_missing(input_text, expected_suffix):
    module = reload_module()
    output = module.filter_content(input_text)
    assert output is not None
    assert expected_suffix.lower() in output.lower()
