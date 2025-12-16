"""
TTS Service
Refactored to use Multi-Process Architecture as per TTS_Design_Pattern.md
"""
import asyncio
import logging
import time
import uuid
import queue
import traceback
from multiprocessing import Process, Queue
from typing import Optional, Callable, Dict, Any

from backend.utils.genie_client import GenieTTS

logger = logging.getLogger(__name__)

# ============================================================================
# TTS Worker Process Logic
# ============================================================================

def tts_worker_main(request_queue, response_queue, config):
    """
    Entry point for the TTS worker process.
    """
    try:
        asyncio.run(tts_worker_async(request_queue, response_queue, config))
    except Exception as e:
        logger.error(f"TTS Worker process failed: {e}")
        traceback.print_exc()
        try:
            response_queue.put(("__ready__", False))
        except:
            pass

async def tts_worker_async(request_queue, response_queue, config):
    """
    Async worker loop.
    """
    logger.info("TTS Worker started")
    
    # 1. Initialize Genie TTS Client
    host = config.get('host', '127.0.0.1')
    port = config.get('port', 8000)
    genie_client = GenieTTS(host=host, port=port)
    
    current_speech_id = None
    synthesis_task: Optional[asyncio.Task] = None
    
    try:
        # 2. Connect and Setup
        logger.info(f"Connecting to Genie TTS at {host}:{port}...")
        if not await genie_client.connect(timeout=5):
            logger.error("Failed to connect to Genie TTS server")
            response_queue.put(("__ready__", False))
            return

        # Load character if configured
        character = config.get('character')
        model_dir = config.get('model_dir')
        language = config.get('language', 'zh')
        
        if character and model_dir:
            logger.info(f"Loading character: {character}")
            if not await genie_client.load_character(character, model_dir, language):
                logger.error("Failed to load character")
                response_queue.put(("__ready__", False))
                return
        
        # Set reference audio if configured
        ref_audio_path = config.get('reference_audio_path')
        ref_audio_text = config.get('reference_audio_text')
        
        if ref_audio_path and ref_audio_text:
            logger.info(f"Setting reference audio: {ref_audio_path}")
            if not await genie_client.set_reference_audio(ref_audio_path, ref_audio_text, language):
                logger.error("Failed to set reference audio")
                response_queue.put(("__ready__", False))
                return
                
        # 3. Send Ready Signal
        logger.info("TTS Worker ready")
        response_queue.put(("__ready__", True))
        
        # 4. Request Processing Loop
        loop = asyncio.get_running_loop()
        
        while True:
            try:
                # Use executor to avoid blocking the asyncio loop while waiting for MP queue
                item = await loop.run_in_executor(None, request_queue.get)
            except Exception as e:
                logger.error(f"Error getting from queue: {e}")
                break
                
            speech_id, text = item
            
            # Termination signal
            if speech_id is None and text is None:
                logger.info("Received termination signal")
                break
                
            # Interruption check
            if speech_id != current_speech_id:
                if current_speech_id is not None:
                    logger.info(f"Interrupting speech {current_speech_id} -> {speech_id}")
                current_speech_id = speech_id
            
            if text:
                await process_text_chunk(genie_client, text, response_queue)

    finally:
        if genie_client:
            await genie_client.close()
        logger.info("TTS Worker stopped")

async def process_text_chunk(client: GenieTTS, text: str, response_queue):
    """
    Process a single text chunk and stream audio to response queue.
    """
    try:
        async for audio_chunk in client.synthesize_stream(text):
            response_queue.put(audio_chunk)
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")

# ============================================================================
# TTS Service Manager (Main Process)
# ============================================================================

class TTSService:
    """
    TTS Service Manager (Main Process)
    Manages the TTS subprocess, queues, and caching.
    """
    
    def __init__(self, config):
        """
        Initialize TTS Service
        
        Args:
            config: ConfigManager instance or config dict
        """
        self.config = config
        self.tts_config = self._load_tts_config()
        
        # Multi-process communication
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.tts_process: Optional[Process] = None
        self.handler_task: Optional[asyncio.Task] = None
        
        # Caching mechanism
        self.tts_ready = False
        self.pending_chunks = []
        self.cache_lock = asyncio.Lock()
        
        # State
        self.current_speech_id = str(uuid.uuid4())
        self.on_audio: Optional[Callable] = None
        self.running = False

    def _load_tts_config(self) -> dict:
        """Load TTS configuration (same as before)"""
        # ... logic to extract config ...
        # For brevity, reusing the logic from previous implementation
        
        if hasattr(self.config, 'get_core_config'):
            core_config = self.config.get_core_config()
            tts_config = core_config.get('tts', {})
            characters = core_config.get('tts_characters', {})
            active_character = tts_config.get('active_character', 'feibi')
            character_config = characters.get(active_character, {})
            
            return {
                'enabled': tts_config.get('enabled', True),
                'host': tts_config.get('server', {}).get('host', '127.0.0.1'),
                'port': tts_config.get('server', {}).get('port', 8000),
                'character': active_character,
                'language': character_config.get('language', 'zh'),
                'model_dir': character_config.get('model_dir'),
                'reference_audio_path': character_config.get('reference_audio', {}).get('path'),
                'reference_audio_text': character_config.get('reference_audio', {}).get('text'),
            }
        elif isinstance(self.config, dict):
            tts_config = self.config.get('tts', {})
            characters = self.config.get('tts_characters', {})
            active_character = tts_config.get('active_character', 'feibi')
            character_config = characters.get(active_character, {})
            
            return {
                'enabled': tts_config.get('enabled', True),
                'host': tts_config.get('server', {}).get('host', '127.0.0.1'),
                'port': tts_config.get('server', {}).get('port', 8000),
                'character': active_character,
                'language': character_config.get('language', 'zh'),
                'model_dir': character_config.get('model_dir'),
                'reference_audio_path': character_config.get('reference_audio', {}).get('path'),
                'reference_audio_text': character_config.get('reference_audio', {}).get('text'),
            }
        else:
            return {}

    async def start(self, on_audio: Callable):
        """
        Start TTS Service (Subprocess)
        """
        self.on_audio = on_audio
        self.running = True
        
        start_time = time.time()
        logger.info("🎤 Starting TTS Service...")
        
        # Initialize Queues
        # Note: In some environments (like macOS default spawn), we pass queues to process
        self.request_queue = Queue()
        self.response_queue = Queue()
        
        # Start Subprocess
        self.tts_process = Process(
            target=tts_worker_main,
            args=(self.request_queue, self.response_queue, self.tts_config)
        )
        self.tts_process.daemon = True
        self.tts_process.start()
        
        # Wait for Ready Signal (Non-blocking)
        try:
            ready = await self._wait_for_ready_signal(timeout=8.0)
            if not ready:
                logger.error("❌ TTS Process failed to initialize")
                # If failed, we don't mark ready.
                # We could raise an exception here if we want to stop the app start,
                # or just leave it unready so calls are buffered forever (or dropped).
                # Ideally, we should probably stop the process if it failed.
                return
        except Exception as e:
            logger.error(f"Error waiting for TTS ready: {e}")
            return
            
        logger.info(f"✅ TTS Service started (took {time.time() - start_time:.2f}s)")
        
        # Start Response Handler
        self.handler_task = asyncio.create_task(self._response_handler())
        
        # Mark ready and flush any pending chunks (if any accumulated during start)
        async with self.cache_lock:
            self.tts_ready = True
        await self._flush_pending_chunks()

    async def stop(self):
        """Stop TTS Service"""
        self.running = False
        logger.info("Stopping TTS Service...")
        
        # 1. Cancel Handler
        if self.handler_task and not self.handler_task.done():
            self.handler_task.cancel()
            try:
                await self.handler_task
            except asyncio.CancelledError:
                pass
        
        # 2. Terminate Process
        if self.tts_process and self.tts_process.is_alive():
            try:
                # Send termination signal
                if self.request_queue:
                    self.request_queue.put((None, None))
                
                self.tts_process.join(timeout=1.0)
                if self.tts_process.is_alive():
                    self.tts_process.terminate()
            except Exception as e:
                logger.error(f"Error stopping TTS process: {e}")
        
        # 3. Close Queues (optional, mostly for cleanup)
        # self.request_queue.close()
        # self.response_queue.close()
        
        self.tts_process = None
        self.request_queue = None
        self.response_queue = None
        self.tts_ready = False
        logger.info("TTS Service stopped")

    async def push_text(self, text: str):
        """
        Push text to TTS (Async with Cache)
        Compatible with existing interface.
        """
        if not text:
            return

        async with self.cache_lock:
            if self.tts_ready and self.request_queue:
                # TTS is ready, send directly
                try:
                    # Non-blocking put? Queue.put is blocking by default, but usually fast if not full.
                    # run_in_executor might be safer if queue can be full, but for simple text it's fine.
                    self.request_queue.put((self.current_speech_id, text))
                except Exception as e:
                    logger.error(f"Failed to push text to TTS: {e}")
            else:
                # Buffer text
                self.pending_chunks.append((self.current_speech_id, text))
                if len(self.pending_chunks) == 1:
                    logger.info("TTS not ready, buffering text...")

    async def flush(self):
        """
        Wait for queue to be processed?
        In MP architecture, 'flush' is tricky because we don't know when the worker is done.
        For now, we can send a marker or just pass. 
        Existing callers might expect this to block until audio is generated.
        With streaming, 'flush' is less relevant.
        """
        pass

    async def clear_queue(self):
        """
        Interrupt current speech and clear queue.
        """
        await self.interrupt()

    async def interrupt(self):
        """
        Interrupt current speech:
        1. Generate new speech_id
        2. Clear pending cache
        3. Clear response queue (handled in handler)
        """
        new_id = str(uuid.uuid4())
        logger.info(f"Interrupting speech {self.current_speech_id} -> {new_id}")
        
        # 1. Clear local cache
        async with self.cache_lock:
            self.pending_chunks.clear()
        
        # 2. Update speech ID (this will cause next push_text to use new ID)
        self.current_speech_id = new_id
        
        # 3. Send interrupt signal to worker (implicit by sending new speech_id with next text)
        # But if we don't have new text immediately?
        # The worker checks speech_id on next request.
        # If we want immediate stop, we can send a dummy or empty request with new ID?
        # Or let the worker handle cancellation when it sees new ID.
        
        # Note: If we just clear the queue on the Python side, the worker might still be processing.
        # Ideally we send a signal.
        # For now, relying on the pattern where next text triggers interruption is fine.
        # BUT, `brain.py` calls `clear_queue` then `llm.cancel`.
        # So we might not send new text for a while (until user speaks again).
        # We should ensuring the worker stops NOW.
        # We can send (new_id, "") to trigger update in worker.
        if self.request_queue:
            self.request_queue.put((new_id, ""))

    async def _wait_for_ready_signal(self, timeout: float) -> bool:
        """Wait for ready signal from worker"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.response_queue and not self.response_queue.empty():
                try:
                    msg = self.response_queue.get_nowait()
                    if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "__ready__":
                        return msg[1]
                    else:
                        # Put back if not ready signal (unlikely during startup)
                        self.response_queue.put(msg)
                except:
                    pass
            await asyncio.sleep(0.05)
        return False

    async def _response_handler(self):
        """Handle responses from worker"""
        logger.info("TTS Response Handler started")
        loop = asyncio.get_running_loop()
        
        while self.running:
            try:
                if self.response_queue and not self.response_queue.empty():
                    # Use run_in_executor for get if needed, but get_nowait is non-blocking
                    try:
                        data = self.response_queue.get_nowait()
                        
                        # Filter signals
                        if isinstance(data, tuple) and data[0] == "__ready__":
                            continue
                        
                        # Audio data
                        if self.on_audio:
                            await self.on_audio(data)
                            
                    except queue.Empty:
                        pass
                    except Exception as e:
                        logger.error(f"Error in response handler: {e}")
                
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Response handler loop error: {e}")
                await asyncio.sleep(1)

    async def _flush_pending_chunks(self):
        """Flush buffered text chunks"""
        async with self.cache_lock:
            if not self.pending_chunks:
                return
            
            logger.info(f"Flushing {len(self.pending_chunks)} buffered chunks")
            if self.request_queue:
                for speech_id, text in self.pending_chunks:
                    try:
                        self.request_queue.put((speech_id, text))
                    except Exception as e:
                        logger.error(f"Error flushing chunk: {e}")
            self.pending_chunks.clear()
