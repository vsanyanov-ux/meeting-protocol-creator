from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable

class BaseAIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'yandex', 'local')"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Specific model identifier (e.g. 'yandexgpt/latest', 'llama3')"""
        pass

    @abstractmethod
    async def transcribe_audio(
        self, 
        audio_path: str, 
        file_id: str, 
        status_updater: Callable[[str, str], None],
        trace: Any
    ) -> Optional[str]:
        """
        Transcribe audio file to text.
        Provider is responsible for any chunking or cloud uploads needed.
        """
        pass

    @abstractmethod
    async def create_protocol(self, transcription: str, status_updater: Optional[Callable[[str, str], None]] = None, file_id: Optional[str] = None, trace: Any = None) -> Dict[str, Any]:
        """
        Generate protocol from text.
        Returns dict with: text (str), latency_ms (int), input_tokens (int), output_tokens (int), messages (list)
        """
        pass

    @abstractmethod
    async def verify_protocol(self, transcription: str, protocol: str, trace: Any = None) -> Dict[str, Any]:
        """
        Verify protocol against transcription.
        Returns dict with: verification_report (str), input_tokens (int), output_tokens (int)
        """
        pass

    async def cleanup(self):
        """
        Optional method to free resources (VRAM/RAM) after a task or queue completion.
        """
        pass

