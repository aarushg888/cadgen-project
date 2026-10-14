from unittest.mock import patch

from cadgen.llm import ChatClient


def test_think_false_uses_native_api_with_toggle():
    c = ChatClient("m", "http://localhost:11435/v1", think=False, max_tokens=1024, temperature=0.2)
    with patch("requests.post") as post:
        post.return_value.json.return_value = {"message": {"content": "hi"}}
        assert c.complete([{"role": "user", "content": "x"}], n=2) == ["hi", "hi"]
        assert post.call_count == 2  # native API has no n>1: one call per sample
        _, kw = post.call_args
        assert kw["json"]["think"] is False
        assert kw["json"]["options"]["num_predict"] == 1024


def test_default_path_uses_openai_client():
    c = ChatClient("m", "http://x/v1")
    assert c.think is None and c._native == "http://x"
