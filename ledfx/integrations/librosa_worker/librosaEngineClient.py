import asyncio
import json
import logging
import os
import sys
import samplerate

import numpy as np

from ledfx.integrations.librosa_worker.protocol import (
    HEADER_STRUCT,
    MSG_TYPE_AUDIO,
    MSG_TYPE_CONFIG,
    MSG_TYPE_SHUTDOWN,
    LEDFX_RATE,
    LIBROSA_SAMPLE_RATE,
    LIBROSA_RESAMPLE_RATIO
)

_LOGGER = logging.getLogger(__name__)


class LibrosaEngineClient:
    """Binary-IPC client to a separate librosa worker process."""

    def __init__(self, config={},python_executable=None, script_path=None):
        self.python_executable = python_executable or sys.executable
        
        # Default to analysis_worker.py in the same directory as this file
        if script_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, "analysis_worker.py")
        
        self.script_path = script_path

        self.process = None
        self._writer = None
        self._reader = None
        self._stderr_reader = None

        self._listen_task = None
        self._stderr_task = None
        self._callbacks = []
        self.config = config
        self.resampler = samplerate.Resampler("sinc_fastest", channels=1)

    async def start(self):
        if self.process is not None:
            return

        _LOGGER.warning("Starting Librosa worker process: %s %s",
                     self.python_executable, self.script_path)

        self.process = await asyncio.create_subprocess_exec(
            self.python_executable,
            self.script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._writer = self.process.stdin
        self._reader = self.process.stdout
        self._stderr_reader = self.process.stderr

        # Listen for JSON feature updates on stdout
        self._listen_task = asyncio.create_task(self._listen_loop())
        # Log worker stderr
        self._stderr_task = asyncio.create_task(self._log_stderr())
        
        # Send initial configuration
        await self.send_config(config=self.config)

    async def stop(self):
        if self.process is None:
            return

        _LOGGER.warning("Stopping Librosa worker process")

        # Send shutdown control message
        try:
            header = HEADER_STRUCT.pack(MSG_TYPE_SHUTDOWN, 0)
            self._writer.write(header)
            await self._writer.drain()
        except Exception as e:
            _LOGGER.error("Error sending shutdown to worker: %r", e)

        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            _LOGGER.error("Worker did not exit in time, killing")
            self.process.kill()

        # Cancel listeners
        for task in (self._listen_task, self._stderr_task):
            if task:
                task.cancel()

        self.process = None
        self._writer = None
        self._reader = None
        self._stderr_reader = None
        self._listen_task = None
        self._stderr_task = None

    def add_callback(self, cb):
        """Register async callback(msg: dict) for feature updates."""
        self._callbacks.append(cb)

    async def _listen_loop(self):
        """Read JSON feature messages from worker stdout."""
        reader = self._reader
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    _LOGGER.error("Bad JSON from worker: %r", text)
                    continue

                for cb in self._callbacks:
                    try:
                        await cb(msg)
                    except Exception as e:
                        _LOGGER.exception("Error in feature callback: %r", e)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.exception("Error in worker listen loop: %r", e)

    async def _log_stderr(self):
        """Log worker stderr for errorging."""
        if not self._stderr_reader:
            return
        try:
            while True:
                line = await self._stderr_reader.readline()
                if not line:
                    break
                sys.stderr.write(f"[librosa-worker] {line.decode(errors='ignore')}")
        except asyncio.CancelledError:
            pass

    async def send_config(self, config={}, sample_rate: int = LIBROSA_SAMPLE_RATE):
        """
        Send configuration to worker as JSON.
        
        sample_rate: Audio sample rate in Hz
        **kwargs: Additional config parameters for future expansion
        """
        if self._writer is None or self.process is None:
            return
        
        config["sample_rate"] = sample_rate
        
        payload = json.dumps(config).encode("utf-8")
        header = HEADER_STRUCT.pack(MSG_TYPE_CONFIG, len(payload))
        
        try:
            self._writer.write(header + payload)
            await self._writer.drain()
            _LOGGER.warning("Sent config to worker: %r", config)
        except Exception as e:
            _LOGGER.error("Error sending config to worker: %r", e)
    
    async def send_audio_block(self, block: np.ndarray):
        """
        Send a mono float32 block to worker as raw bytes.

        block: np.ndarray, dtype float32, shape (n_samples,)
        """
        if self._writer is None or self.process is None:
            return

        block = self.resampler.process(
            block, 
            LIBROSA_RESAMPLE_RATIO)
            
        # Ensure dtype and contiguity
        if block.dtype != np.float32:
            block = block.astype(np.float32, copy=False)
        block = np.ascontiguousarray(block)

        payload = block.tobytes()
        header = HEADER_STRUCT.pack(MSG_TYPE_AUDIO, len(payload))

        try:
            self._writer.write(header + payload)
            await self._writer.drain()
        except Exception as e:
            _LOGGER.error("Error sending audio block to worker: %r", e)
