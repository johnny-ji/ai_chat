import os
import pytest
from unittest.mock import patch, MagicMock
from model_manager import download_model, ensure_models


def test_download_model_already_exists(tmp_path):
    model_name = "test/model"
    model_dir = tmp_path / "test" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "dummy.txt").write_text("dummy")

    result = download_model(model_name, "v1", str(tmp_path))
    assert result == os.path.join(str(tmp_path), model_name)


def test_ensure_models_downloads_missing(tmp_path):
    config = {
        "models_dir": str(tmp_path),
        "asr_model_online": "asr/model",
        "asr_model_online_revision": "v1",
        "vad_model": "vad/model",
        "vad_model_revision": "v1",
        "punc_model": "punc/model",
        "punc_model_revision": "v1",
    }

    with patch("model_manager.download_model") as mock_download:
        mock_download.return_value = "mocked/path"
        ensure_models(config)
        assert mock_download.call_count == 3
