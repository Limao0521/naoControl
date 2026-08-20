from nao_gateway.sensor_hub import extract_first_jpeg


def test_extracts_complete_jpeg_from_mjpeg_chunks():
    payload = b"--boundary\r\nheaders\r\n\xff\xd8jpeg-data\xff\xd9\r\n"

    assert extract_first_jpeg(payload) == b"\xff\xd8jpeg-data\xff\xd9"


def test_incomplete_frame_returns_none():
    assert extract_first_jpeg(b"\xff\xd8partial") is None
