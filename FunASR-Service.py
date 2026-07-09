import asyncio
import gc
import json
import websockets
import time
import argparse
import os
import functools
import yaml
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import torch
from funasr import AutoModel
from modelscope import snapshot_download


def load_config(env: str, config_path: str = None) -> dict:
    if config_path is None:
        config_path = f"configs/{env}.yaml"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config.get("device") == "auto":
        config["device"] = "cuda" if torch.cuda.is_available() else \
                          ("mps" if torch.backends.mps.is_available() else "cpu")
    return config


def download_model(model_name: str, model_revision: str, local_dir: str) -> str:
    # ModelScope snapshot_download stores at {cache_dir}/models/{normalized_name}/snapshots/{revision}/
    normalized = model_name.replace("/", "--")
    snapshot_path = os.path.join(local_dir, "models", normalized, "snapshots", model_revision)
    if os.path.exists(snapshot_path) and os.listdir(snapshot_path):
        return snapshot_path

    try:
        print(f"正在下载模型: {model_name} (revision: {model_revision})")
        return snapshot_download(model_name, revision=model_revision, cache_dir=local_dir)
    except Exception as e:
        raise RuntimeError(f"模型下载失败: {model_name} (revision: {model_revision}). 错误: {e}") from e


def ensure_models(config: dict) -> dict:
    models_dir = config.get("models_dir", "models")
    os.makedirs(models_dir, exist_ok=True)
    return {
        "asr_model_online": download_model(config["asr_model_online"], config["asr_model_online_revision"], models_dir),
        "vad_model": download_model(config["vad_model"], config["vad_model_revision"], models_dir),
        "punc_model": download_model(config["punc_model"], config["punc_model_revision"], models_dir),
    }


parser = argparse.ArgumentParser()
parser.add_argument("--env", type=str, default="development", help="环境名称")
parser.add_argument("--config", type=str, default=None, help="配置文件路径")
args = parser.parse_args()

config = load_config(args.env, args.config)
model_paths = ensure_models(config)

websocket_users = set()


model_vad = AutoModel(
    model=model_paths["vad_model"],
    model_revision=config["vad_model_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
    disable_update=True,
)
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()

model_asr_streaming = AutoModel(
    model=model_paths["asr_model_online"],
    model_revision=config["asr_model_online_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
    disable_update=True,
)
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()

model_punc = AutoModel(
    model=model_paths["punc_model"],
    model_revision=config["punc_model_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
    disable_update=True,
)

print("model loaded! (now supports multi-client with non-blocking inference)")


# ====== 线程池 + 并发阈值（核心）======
EXECUTOR = ThreadPoolExecutor(max_workers=int(config.get("worker_threads", 8)))

SEM_VAD = asyncio.Semaphore(max(1, int(config.get("concurrent_vad", 4))))
SEM_ASR_ONLINE = asyncio.Semaphore(max(1, int(config.get("concurrent_asr_online", 4))))
SEM_PUNC = asyncio.Semaphore(max(1, int(config.get("concurrent_punc", 1))))


def _pcm_duration_ms(pcm_bytes: bytes, fs: int, ch: int = 1, sampwidth: int = 2) -> int:
    """根据 fs/ch/sampwidth 计算 PCM 时长，避免写死 16k -> 32 bytes/ms。"""
    if not pcm_bytes:
        return 0
    bytes_per_ms = (fs * ch * sampwidth) / 1000.0
    if bytes_per_ms <= 0:
        return 0
    return int(len(pcm_bytes) / bytes_per_ms)


# 能量检测：RMS 低于此值视为静音（int16 量程 0-32768，300 适合低噪麦克风）
_SILENCE_RMS_THRESHOLD = int(config.get("silence_rms_threshold", 300))
# 能量静音连续时长超过此值(ms)则强制触发 is_final，作为 VAD max_end_silence_time 的兜底
_SILENCE_TIMEOUT_MS = int(config.get("silence_timeout_ms", 1000))


def _frame_rms(pcm_bytes: bytes) -> float:
    """返回 PCM int16 帧的 RMS 能量。"""
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2))) if len(arr) else 0.0


def _safe_int(v, default):
    try:
        return int(v)
    except Exception:
        return default


async def run_blocking(fn, *a, sem: asyncio.Semaphore | None = None, **kw):
    """
    把阻塞函数丢线程池执行，避免卡 event loop。
    sem 用于限流（避免 GPU / 模型被打爆）。
    """
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *a, **kw)
    if sem is None:
        return await loop.run_in_executor(EXECUTOR, call)
    async with sem:
        return await loop.run_in_executor(EXECUTOR, call)


def _generate_sync(model, audio_or_text, status_dict):
    # 注意：status_dict 里包含 cache，会被 generate 更新
    return model.generate(input=audio_or_text, **status_dict)


async def ws_reset(websocket):
    print("ws reset now, total num is ", len(websocket_users))

    websocket.status_dict_asr_online["cache"] = {}
    websocket.status_dict_asr_online["is_final"] = True
    websocket.status_dict_vad["cache"] = {}
    websocket.status_dict_vad["is_final"] = True
    websocket.status_dict_punc["cache"] = {}

    await websocket.close()


async def clear_websocket():
    for websocket in list(websocket_users):
        await ws_reset(websocket)
    websocket_users.clear()


async def ws_serve(websocket, path=None):
    if path is None:
        path = getattr(websocket, "path", None)

    frames_asr_online = []
    websocket_users.add(websocket)

    websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
    websocket.status_dict_vad = {"cache": {}, "is_final": False, "max_end_silence_time": 1000}
    websocket.status_dict_punc = {"cache": {}}

    websocket.chunk_interval = 10
    websocket.vad_pre_idx = 0
    websocket.wav_name = "microphone"
    websocket.is_speaking = True  # 初始化
    speech_start = False
    speech_end_i = -1
    consecutive_silence_ms = 0  # 连续静音时长(ms)，用于能量兜底超时

    print(f"new user connected, total={len(websocket_users)}", flush=True)

    try:
        async for message in websocket:
            if isinstance(message, str):
                messagejson = json.loads(message)

                print(f"[CONFIG] received: {messagejson}", flush=True)

                if "is_speaking" in messagejson:
                    websocket.is_speaking = bool(messagejson["is_speaking"])
                    # When client signals stop, flush remaining buffered audio immediately
                    if not websocket.is_speaking and frames_asr_online:
                        print("[INFO] is_speaking=False received, flushing remaining audio...", flush=True)
                        websocket.status_dict_asr_online["is_final"] = True
                        audio_in = b"".join(frames_asr_online)
                        frames_asr_online = []
                        try:
                            text = await async_asr_online(websocket, audio_in)
                        except Exception as e:
                            print(f"[ERROR] ASR flush on stop: {e}")
                            text = ""
                        if text and model_punc:
                            try:
                                punc_out = await run_blocking(
                                    _generate_sync, model_punc, text,
                                    websocket.status_dict_punc, sem=SEM_PUNC,
                                )
                                text = punc_out[0].get("text", text)
                            except Exception as e:
                                print(f"[ERROR] Punc flush on stop: {e}")
                        if text:
                            print(f"[ASR final/flush] {text}", flush=True)
                            await websocket.send(json.dumps({
                                "text": text,
                                "wav_name": websocket.wav_name,
                                "is_final": True,
                            }, ensure_ascii=False))
                        # Reset state
                        chunk_size_backup = websocket.status_dict_asr_online.get("chunk_size")
                        speech_start = False
                        speech_end_i = -1
                        consecutive_silence_ms = 0
                        websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
                        if chunk_size_backup:
                            websocket.status_dict_asr_online["chunk_size"] = chunk_size_backup
                        websocket.status_dict_vad = {"cache": {}, "is_final": False, "max_end_silence_time": 1000}
                        websocket.vad_pre_idx = 0

                if "chunk_interval" in messagejson:
                    websocket.chunk_interval = int(messagejson["chunk_interval"])

                if "wav_name" in messagejson:
                    websocket.wav_name = messagejson.get("wav_name") or websocket.wav_name

                if "chunk_size" in messagejson:
                    chunk_size = messagejson["chunk_size"]
                    if isinstance(chunk_size, str):
                        chunk_size = [x.strip() for x in chunk_size.split(",") if x.strip()]
                    websocket.status_dict_asr_online["chunk_size"] = [int(x) for x in chunk_size]

                if "encoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["encoder_chunk_look_back"] = messagejson["encoder_chunk_look_back"]

                if "decoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["decoder_chunk_look_back"] = messagejson["decoder_chunk_look_back"]

                if "hotwords" in messagejson:
                    websocket.status_dict_asr_online["hotword"] = messagejson["hotwords"]

                continue

            # Bug fix: guard against audio arriving before config is sent
            if "chunk_size" not in websocket.status_dict_asr_online:
                print("[WARN] chunk_size not set yet, skip audio frame.")
                continue

            # Confirm audio is being received (print every 50 frames ≈ 3s)
            if len(frames_asr_online) % 50 == 0:
                print(f"[AUDIO] receiving frames, buffer={len(frames_asr_online)}", flush=True)

            # Bug fix: set VAD chunk_size so streaming VAD works correctly
            try:
                websocket.status_dict_vad["chunk_size"] = int(
                    websocket.status_dict_asr_online["chunk_size"][1] * 60 / websocket.chunk_interval
                )
            except Exception as e:
                print(f"[WARN] Failed to set VAD chunk_size: {e}")

            pcm = message
            duration_ms = _pcm_duration_ms(pcm, fs=16000, ch=1, sampwidth=2)
            websocket.vad_pre_idx += duration_ms

            # 累积音频帧
            frames_asr_online.append(pcm)

            # VAD 检测
            try:
                speech_start_i, speech_end_i = await async_vad(websocket, pcm)
            except Exception as e:
                print(f"[ERROR] VAD failed: {e}")
                speech_start_i, speech_end_i = -1, -1

            if speech_start_i != -1:
                speech_start = True
                consecutive_silence_ms = 0
                print(f"[VAD] speech start at {speech_start_i}ms", flush=True)
            if speech_end_i != -1:
                print(f"[VAD] speech end at {speech_end_i}ms", flush=True)

            # 能量兜底：VAD 参数不生效时用 RMS 能量检测静音
            if speech_start and speech_end_i == -1:
                rms = _frame_rms(pcm)
                if rms < _SILENCE_RMS_THRESHOLD:
                    consecutive_silence_ms += duration_ms
                else:
                    consecutive_silence_ms = 0
                if consecutive_silence_ms >= _SILENCE_TIMEOUT_MS:
                    print(f"[INFO] Energy silence {consecutive_silence_ms}ms (RMS={rms:.0f}), forcing final", flush=True)
                    speech_end_i = 1  # 任意非-1值，触发 is_final

            is_final = (speech_end_i != -1) or (not websocket.is_speaking)
            websocket.status_dict_asr_online["is_final"] = is_final

            # 定期触发流式ASR（非最终结果）
            if (len(frames_asr_online) % websocket.chunk_interval == 0) and not is_final:
                audio_in = b"".join(frames_asr_online)
                frames_asr_online = []  # Bug fix: clear buffer after each chunk, not just on is_final
                try:
                    text = await async_asr_online(websocket, audio_in)
                except Exception as e:
                    print(f"[ERROR] ASR online (partial) failed: {e}")
                    text = ""
                if text:
                    print(f"[ASR partial] {text}", flush=True)
                    msg = {
                        "text": text,
                        "wav_name": websocket.wav_name,
                        "is_final": False,
                    }
                    await websocket.send(json.dumps(msg, ensure_ascii=False))

            # 语音结束处理：获取最终结果并加标点
            if is_final:
                audio_in = b"".join(frames_asr_online)
                frames_asr_online = []  # Clear remaining frames
                try:
                    text = await async_asr_online(websocket, audio_in)
                except Exception as e:
                    print(f"[ERROR] ASR online (final) failed: {e}")
                    text = ""

                if text and model_punc:
                    try:
                        punc_out = await run_blocking(
                            _generate_sync,
                            model_punc,
                            text,
                            websocket.status_dict_punc,
                            sem=SEM_PUNC,
                        )
                        text = punc_out[0].get("text", text)
                    except Exception as e:
                        print(f"[ERROR] Punctuation failed: {e}")

                if text:
                    print(f"[ASR final] {text}", flush=True)
                    msg = {
                        "text": text,
                        "wav_name": websocket.wav_name,
                        "is_final": True,
                    }
                    await websocket.send(json.dumps(msg, ensure_ascii=False))

                # Bug fix: preserve chunk_size when resetting state between speech segments
                chunk_size_backup = websocket.status_dict_asr_online.get("chunk_size")
                speech_start = False
                speech_end_i = -1
                consecutive_silence_ms = 0
                websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
                if chunk_size_backup:
                    websocket.status_dict_asr_online["chunk_size"] = chunk_size_backup
                websocket.status_dict_vad = {"cache": {}, "is_final": False, "max_end_silence_time": 1000}
                websocket.vad_pre_idx = 0

    except websockets.ConnectionClosed:
        print("ConnectionClosed...")
    except Exception as e:
        print("Exception:", e)
    finally:
        await ws_reset(websocket)
        websocket_users.discard(websocket)


async def async_vad(websocket, audio_in: bytes):
    # model_vad.generate 是阻塞的，必须 offload
    out = await run_blocking(_generate_sync, model_vad, audio_in, websocket.status_dict_vad, sem=SEM_VAD)
    segments_result = out[0].get("value", [])

    speech_start = -1
    speech_end = -1

    if len(segments_result) == 0 or len(segments_result) > 1:
        return speech_start, speech_end
    if segments_result[0][0] != -1:
        speech_start = segments_result[0][0]
    if segments_result[0][1] != -1:
        speech_end = segments_result[0][1]
    return speech_start, speech_end


async def async_asr_online(websocket, audio_in: bytes) -> str:
    if len(audio_in) <= 0:
        return ""

    rec_out = await run_blocking(
        _generate_sync,
        model_asr_streaming,
        audio_in,
        websocket.status_dict_asr_online,
        sem=SEM_ASR_ONLINE,
    )
    rec_result = rec_out[0]
    return rec_result.get("text", "")


# ===================== 启动服务 =====================

async def main():
    server = await websockets.serve(
        ws_serve,
        config["host"],
        config["port"],
        subprotocols=["binary"],
        ping_interval=None,
    )

    print(f"WS server started at ws://{config['host']}:{config['port']}")
    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            EXECUTOR.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
