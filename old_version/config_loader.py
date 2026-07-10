import os
import yaml
import torch
from typing import Optional


CONFIG_DIR = "configs"


def detect_device(config: dict) -> dict:
    """处理 device=auto，自动选择可用的后端。"""
    device = config.get("device", "auto")
    if device != "auto":
        return config

    if torch.cuda.is_available():
        config["device"] = "cuda"
    elif torch.backends.mps.is_available():
        config["device"] = "mps"
    else:
        config["device"] = "cpu"
    return config


def load_config(env: str, config_path: Optional[str] = None) -> dict:
    """从 YAML 文件加载配置。"""
    if config_path is None:
        config_path = os.path.join(CONFIG_DIR, f"{env}.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"配置文件格式错误: {config_path}")

    config = detect_device(config)
    return config
