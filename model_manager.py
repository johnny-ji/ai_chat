import os
from modelscope import snapshot_download


def download_model(model_name: str, model_revision: str, local_dir: str) -> str:
    """检查模型是否已下载，未下载则自动下载。"""
    local_path = os.path.join(local_dir, model_name)
    if os.path.exists(local_path) and os.listdir(local_path):
        return local_path

    try:
        print(f"正在下载模型: {model_name} (revision: {model_revision})")
        return snapshot_download(
            model_name,
            revision=model_revision,
            cache_dir=local_dir,
        )
    except Exception as e:
        raise RuntimeError(f"模型下载失败: {model_name} (revision: {model_revision}). 错误: {e}") from e


def ensure_models(config: dict):
    """确保所有模型已下载。"""
    models_dir = config.get("models_dir", "./models")
    os.makedirs(models_dir, exist_ok=True)

    models = [
        (config["asr_model_online"], config["asr_model_online_revision"]),
        (config["vad_model"], config["vad_model_revision"]),
        (config["punc_model"], config["punc_model_revision"]),
    ]

    for model_name, revision in models:
        download_model(model_name, revision, models_dir)
