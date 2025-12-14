import logging

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.on_transcript = None
        self.on_vad_trigger = None

    async def start(self, on_transcript, on_vad_trigger):
        self.on_transcript = on_transcript
        self.on_vad_trigger = on_vad_trigger
        self.running = True
        logger.info("ASR Service started (Mock)")
        # 模拟：实际逻辑中会监听麦克风或 WebSocket 音频流

    async def stop(self):
        self.running = False
        logger.info("ASR Service stopped")
