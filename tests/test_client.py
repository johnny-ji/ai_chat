import pytest
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ====== 通过 importlib 导入带连字符的文件 ======
import importlib.util
client_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FunASR-Client.py")
spec = importlib.util.spec_from_file_location("funasr_client", client_path)
funasr_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(funasr_client)

parse_args = funasr_client.parse_args
save_text = funasr_client.save_text


def test_parse_args_default():
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 10095


def test_parse_args_custom():
    args = parse_args(["--host", "192.168.1.1", "--port", "8080"])
    assert args.host == "192.168.1.1"
    assert args.port == 8080


def test_save_text(tmp_path):
    path = tmp_path / "test.txt"
    save_text("hello", str(path))
    content = path.read_text(encoding="utf-8")
    assert "hello" in content
    # 验证包含时间戳格式
    assert content.startswith("[")
    assert "]" in content
