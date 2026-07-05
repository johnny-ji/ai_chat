# 学习测试使用
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess



MODEL_ROOT = "/Users/jiqiang/ai_chat/models"
# 1. 加载模型
model = AutoModel(model=MODEL_ROOT + "/iic/SenseVoiceSmall", 
                  vad_model=MODEL_ROOT + "/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", 
                  spk_model=MODEL_ROOT + "/iic/speech_campplus_sv_zh-cn_16k-common", 
                  #punc_model=MODEL_ROOT + "/iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727",
                  device="mps", 
                  disable_update=True)  # use device="cpu" or device="mps" or device="cuda" based on your environment
# 2. 进行语音识别
result = model.generate(
    input="https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav",
    batch_size_s=300,
)

# 3. 输出结果
for seg in result[0]["sentence_info"]:
    print(f"[{seg['start']/1000:.1f}s] Speaker {seg['spk']}: {rich_transcription_postprocess(seg['sentence'])}")


