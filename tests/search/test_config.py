"""Settings smoke for slice 2a additions."""
from backend.config import Settings, get_settings


def test_settings_defaults_include_search_and_deepseek():
    # Construct directly with _env_file=None to test pure code defaults,
    # bypassing any .env file that may exist in the project root.
    s = Settings(_env_file=None)
    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.deepseek_model == "deepseek-chat"
    assert s.search_chroma_dir == "./data/chroma"
    assert s.search_embed_model == "BAAI/bge-small-zh-v1.5"
    assert s.search_rerank_threshold == 0.15
    assert s.search_rrf_k == 60
    # api key 没有默认值，留空字符串
    assert s.deepseek_api_key == ""


def test_settings_reads_env_overrides(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SEARCH_RRF_K", "30")
    s = get_settings()
    assert s.deepseek_api_key == "sk-test"
    assert s.search_rrf_k == 30
