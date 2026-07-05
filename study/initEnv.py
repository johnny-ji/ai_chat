from modelscope import snapshot_download

# 预先下载模型并指定缓存目录，避免每次运行都重新下载模型
MODEL_ROOT = "/Users/jiqiang/ai_chat/models"
# ASR模型
sensevoice_dir = snapshot_download(
    "iic/SenseVoiceSmall",
    cache_dir=MODEL_ROOT
)

# VAD模型
vad_dir = snapshot_download(
    "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    cache_dir=MODEL_ROOT
)

# 说话人识别模型
spk_dir = snapshot_download(
    "iic/speech_campplus_sv_zh-cn_16k-common",
    cache_dir=MODEL_ROOT
)

# 断句模型
punc_dir = snapshot_download(
    "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727",
    cache_dir=MODEL_ROOT
)