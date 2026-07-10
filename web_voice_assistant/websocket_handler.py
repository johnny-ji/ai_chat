"""websocket_handler.py - WebSocket 连接处理模块"""
import json
import asyncio
import base64
from typing import Dict, Set
from fastapi import WebSocket

from chat_manager import ChatManager
from audio_pipeline import AudioPipeline


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.chat_manager = ChatManager()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f'[WebSocket] 新连接，当前连接数: {len(self.active_connections)}')

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f'[WebSocket] 断开连接，当前连接数: {len(self.active_connections)}')

    async def send_message(self, websocket: WebSocket, message: Dict):
        """发送消息到客户端"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f'[WebSocket] 发送消息失败: {e}')


class ConnectionHandler:
    """单个连接处理器"""

    def __init__(self, websocket: WebSocket, manager: WebSocketManager):
        self.websocket = websocket
        self.manager = manager
        self.audio_pipeline: AudioPipeline = None
        self.is_recording = False
        self.current_user_text = ""
        self.is_processing = False

    async def handle(self):
        """处理 WebSocket 连接"""
        try:
            while True:
                data = await self.websocket.receive_text()
                message = json.loads(data)
                await self.process_message(message)
        except Exception as e:
            print(f'[ConnectionHandler] 连接异常: {e}')
        finally:
            self.cleanup()

    async def process_message(self, message: Dict):
        """处理收到的消息"""
        msg_type = message.get('type')

        if msg_type == 'control':
            await self.handle_control(message)
        elif msg_type == 'audio':
            await self.handle_audio(message)

    async def handle_control(self, message: Dict):
        """处理控制消息"""
        action = message.get('action')

        if action == 'start_recording':
            await self.start_recording()
        elif action == 'stop_recording':
            await self.stop_recording()

    async def handle_audio(self, message: Dict):
        """处理音频数据"""
        if not self.is_recording:
            return

        audio_data = base64.b64decode(message.get('data', ''))

        if self.audio_pipeline:
            self.audio_pipeline.send_audio(audio_data)

    async def start_recording(self):
        """开始录音"""
        if self.is_recording:
            return

        self.is_recording = True
        self.current_user_text = ""

        self.audio_pipeline = AudioPipeline(
            on_asr_text=self.on_asr_result,
            on_tts_audio=self.on_tts_audio
        )
        self.audio_pipeline.start_asr()

        await self.manager.send_message(self.websocket, {
            'type': 'status',
            'state': 'recording'
        })

        print('[ConnectionHandler] 开始录音')

    async def stop_recording(self):
        """停止录音"""
        if not self.is_recording:
            return

        self.is_recording = False

        if self.audio_pipeline:
            self.audio_pipeline.stop_asr()

        await self.manager.send_message(self.websocket, {
            'type': 'status',
            'state': 'thinking'
        })

        if self.current_user_text.strip() and not self.is_processing:
            asyncio.create_task(self.process_conversation())

        print('[ConnectionHandler] 停止录音')

    def on_asr_result(self, text: str, is_final: bool):
        """ASR 识别结果回调"""
        if is_final:
            self.current_user_text = text
            asyncio.create_task(self.manager.send_message(self.websocket, {
                'type': 'transcription',
                'text': text,
                'is_final': True
            }))

    async def process_conversation(self):
        """处理对话流程"""
        self.is_processing = True

        try:
            self.audio_pipeline.start_tts()

            await self.manager.send_message(self.websocket, {
                'type': 'ai_text',
                'text': '',
                'done': False
            })

            full_response = ""
            async for text_chunk in self.manager.chat_manager.stream_chat(self.current_user_text):
                full_response += text_chunk

                await self.manager.send_message(self.websocket, {
                    'type': 'ai_text',
                    'text': full_response,
                    'done': False
                })

                self.audio_pipeline.send_text_for_tts(text_chunk)

            self.audio_pipeline.flush_tts()

            await self.manager.send_message(self.websocket, {
                'type': 'ai_text',
                'text': full_response,
                'done': True
            })

            await self.manager.send_message(self.websocket, {
                'type': 'complete'
            })

            await self.manager.send_message(self.websocket, {
                'type': 'status',
                'state': 'idle'
            })

        except Exception as e:
            print(f'[ConnectionHandler] 对话处理失败: {e}')
            await self.manager.send_message(self.websocket, {
                'type': 'error',
                'message': '对话处理失败，请重试'
            })
            await self.manager.send_message(self.websocket, {
                'type': 'status',
                'state': 'idle'
            })

        finally:
            self.is_processing = False
            self.current_user_text = ""

    def on_tts_audio(self, pcm_data: bytes):
        """TTS 音频数据回调"""
        asyncio.create_task(self.manager.send_message(self.websocket, {
            'type': 'audio',
            'data': base64.b64encode(pcm_data).decode('utf-8')
        }))

    def cleanup(self):
        """清理资源"""
        if self.audio_pipeline:
            self.audio_pipeline.stop_asr()
            self.audio_pipeline.stop_tts()
            self.audio_pipeline = None


ws_manager = WebSocketManager()


async def handle_websocket(websocket: WebSocket):
    """处理 WebSocket 连接"""
    await ws_manager.connect(websocket)

    try:
        handler = ConnectionHandler(websocket, ws_manager)
        await handler.handle()
    finally:
        ws_manager.disconnect(websocket)
