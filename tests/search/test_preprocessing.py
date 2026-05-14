"""tests/search/test_preprocessing.py"""
from backend.search.preprocessing import tokenize, RNO_TERMS


def test_tokenize_protects_rno_compound_terms():
    """覆盖强度/信噪比/掉话率不能被切散。"""
    tokens = tokenize("每个小区每小时的平均覆盖强度")
    assert "覆盖强度" in tokens
    assert "覆盖" not in tokens  # 没被切散就不会单独出现
    assert "强度" not in tokens


def test_tokenize_uppercase_acronyms_lowercased():
    tokens = tokenize("RSRP 和 SINR 的均值")
    assert "rsrp" in tokens
    assert "sinr" in tokens


def test_tokenize_strips_empty_and_whitespace():
    tokens = tokenize("  覆盖强度   ")
    assert tokens == ["覆盖强度"]


def test_rno_terms_includes_all_required_keywords():
    required = {
        "覆盖强度", "信噪比", "掉话率", "切换成功率", "吞吐量",
        "RSRP", "SINR", "RSRQ", "QoE", "切换", "会话",
    }
    assert required.issubset(set(RNO_TERMS))


def test_tokenize_handles_empty_string():
    assert tokenize("") == []
