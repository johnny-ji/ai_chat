import pytest
import os
from config_loader import load_config, detect_device


def test_detect_device_auto():
    config = {"device": "auto"}
    detect_device(config)
    assert config["device"] in ["cuda", "mps", "cpu"]


def test_detect_device_explicit():
    config = {"device": "cpu"}
    detect_device(config)
    assert config["device"] == "cpu"


def test_load_config_development():
    config = load_config("development")
    assert config["host"] == "0.0.0.0"
    assert config["port"] == 10095
    assert "models_dir" in config


def test_load_config_missing():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent")
