from llm_cookie_bridge.utils import compute_delta, parse_cookie_header, parse_length_prefixed_json_frames


def test_parse_cookie_header() -> None:
    parsed = parse_cookie_header("a=1; sessionKey=abc123; theme=dark")
    assert parsed == {"a": "1", "sessionKey": "abc123", "theme": "dark"}


def test_compute_delta_prefers_suffix() -> None:
    assert compute_delta("hello world", "hello") == " world"


def test_parse_length_prefixed_json_frames() -> None:
    payload = '[1,2]'
    frames, rest = parse_length_prefixed_json_frames(f"{len(payload)}\n{payload}\n")
    assert frames == [1, 2]
    assert rest == ""
