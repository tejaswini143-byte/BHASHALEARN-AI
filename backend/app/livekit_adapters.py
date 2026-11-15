"""Turn-based LiveKit STT/TTS adapters for Gnani's REST-only Prisma and Timbre APIs."""
import asyncio
import sys
import tempfile
import uuid
import wave
from pathlib import Path

from livekit import rtc
from livekit.agents import LanguageCode, stt, tts
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from livekit.agents.utils.audio import AudioBuffer, AudioByteStream, combine_frames

from .settings import settings

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "pocs/poc01_prisma_stt", ROOT / "pocs/poc02_timbre_tts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from prisma_stt import PrismaConfig, PrismaSTTAdapter  # noqa: E402
from timbre_tts import TimbreConfig, TimbreTTSAdapter  # noqa: E402


class GnaniPrismaSTT(stt.STT):
    """Non-streaming STT: VAD batches a turn, Prisma receives one PCM WAV REST request."""

    def __init__(self):
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        self._adapter = None
        if settings.gnani_api_key:
            self._adapter = PrismaSTTAdapter(PrismaConfig(url=settings.gnani_stt_url, api_key=settings.gnani_api_key,
                                                            timeout_seconds=30))

    @property
    def model(self) -> str:
        return "prisma-v3.0"

    @property
    def provider(self) -> str:
        return "gnani"

    async def _recognize_impl(self, buffer: AudioBuffer, *, language="te-IN", conn_options):
        if self._adapter is None:
            raise RuntimeError("GNANI_API_KEY is not configured for Prisma STT")
        frame = combine_frames(buffer) if isinstance(buffer, list) else buffer
        if frame.samples_per_channel <= 0 or frame.samples_per_channel / frame.sample_rate > 30:
            raise ValueError("Prisma accepts non-empty audio turns up to 30 seconds")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = Path(tmp.name)
        try:
            with wave.open(str(audio_path), "wb") as wav:
                wav.setnchannels(frame.num_channels)
                wav.setsampwidth(2)
                wav.setframerate(frame.sample_rate)
                wav.writeframes(bytes(frame.data))
            result = await asyncio.wait_for(asyncio.to_thread(self._adapter.transcribe, audio_path), timeout=35)
        finally:
            audio_path.unlink(missing_ok=True)
        detected = result.language or str(language or "te-IN")
        try:
            detected = LanguageCode(detected)
        except ValueError:
            detected = LanguageCode(str(language or "te-IN"))
        return SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, request_id=str(uuid.uuid4()),
                           alternatives=[SpeechData(language=detected, text=result.text)])


class GnaniTimbreTTS(tts.TTS):
    """Non-streaming TTS: each completed LiveKit text segment becomes a REST WAV request."""

    def __init__(self, language: str = "te-IN"):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=48000, num_channels=1)
        self.language = language
        self._adapter = None
        if settings.gnani_api_key:
            self._adapter = TimbreTTSAdapter(TimbreConfig(api_key=settings.gnani_api_key,
                url=settings.gnani_tts_url, timeout_seconds=30))

    @property
    def model(self) -> str:
        return "timbre-v2.5"

    @property
    def provider(self) -> str:
        return "gnani"

    def synthesize(self, text: str, *, conn_options):
        return GnaniTimbreChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class GnaniTimbreChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        provider: GnaniTimbreTTS = self._tts  # type: ignore[assignment]
        if provider._adapter is None:
            raise RuntimeError("GNANI_API_KEY is not configured for Timbre TTS")
        language = provider.language
        if language == "mixed":
            language = "auto"
        voice = "Suhana" if language in {"te-IN", "auto"} else "Kaveri"
        wav_data = await asyncio.wait_for(asyncio.to_thread(provider._adapter.synthesize,
            self.input_text, language, voice), timeout=35)
        with wave.open(__import__("io").BytesIO(wav_data), "rb") as wav:
            if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
                raise ValueError("Timbre adapter returned an unsupported WAV encoding")
            sample_rate, channels = wav.getframerate(), wav.getnchannels()
            pcm = wav.readframes(wav.getnframes())
        output_emitter.initialize(request_id=str(uuid.uuid4()), sample_rate=sample_rate,
                                  num_channels=channels, mime_type="audio/pcm", stream=False)
        byte_stream = AudioByteStream(sample_rate, channels)
        frames = byte_stream.write(pcm) + byte_stream.flush()
        for frame in frames:
            output_emitter.push_frame(frame)
        output_emitter.flush()
