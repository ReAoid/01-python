import asyncio
import logging

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, config):
        self.config = config
        self.queue = asyncio.Queue()
        self.running = False
        self.on_audio = None

    async def start(self, on_audio):
        self.on_audio = on_audio
        self.running = True
        asyncio.create_task(self._process_queue())
        logger.info("TTS Service started (Mock)")

    async def stop(self):
        self.running = False
        logger.info("TTS Service stopped")

    async def push_text(self, text: str):
        await self.queue.put(text)

    async def flush(self):
        # 等待队列处理完毕或清空缓冲
        pass

    async def clear_queue(self):
        # 清空待播放队列
        while not self.queue.empty():
            self.queue.get_nowait()

    async def _process_queue(self):
        while self.running:
            text = await self.queue.get()
            # 模拟合成耗时
            # await asyncio.sleep(0.1) 
            if self.on_audio:
                # 模拟音频数据
                await self.on_audio(f"Audio chunk for: {text}".encode('utf-8'))
            self.queue.task_done()
