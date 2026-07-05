from pathlib import Path

from pydantic import Field

from nvkit_core import missing_credentials_message, require_env
from nvkit_core.compat import Builder, FunctionBaseConfig, FunctionInfo, register_function

ENV_VARS = ("RIVA_SERVER",)


class TranscribeAudioConfig(FunctionBaseConfig, name="nvkit_transcribe_audio"):
    language_code: str = Field(default="en-US", description="ASR language code")
    enable_punctuation: bool = Field(default=True, description="Add punctuation to transcript")


@register_function(config_type=TranscribeAudioConfig)
async def transcribe_audio(config: TranscribeAudioConfig, builder: Builder):

    async def _transcribe(audio_path: str) -> str:
        """Transcribe an audio file (interview, briefing, press event) to text."""
        creds = require_env(*ENV_VARS)
        if creds is None:
            return missing_credentials_message("nvkit_transcribe_audio", *ENV_VARS)

        path = Path(audio_path).expanduser()
        if not path.is_file():
            return f"[nvkit_transcribe_audio] Audio file not found: {audio_path}"

        # TODO(nvkit): call a Riva / Parakeet ASR NIM over gRPC, e.g.
        #   import riva.client
        #   auth = riva.client.Auth(uri=creds["RIVA_SERVER"])
        #   asr = riva.client.ASRService(auth)
        #   cfg = riva.client.RecognitionConfig(
        #       language_code=config.language_code,
        #       enable_automatic_punctuation=config.enable_punctuation)
        #   response = asr.offline_recognize(path.read_bytes(), cfg)
        # Keeping audio on NVIDIA infrastructure avoids sending potentially
        # embargoed PR material to third-party transcription services.
        raise NotImplementedError("Riva ASR call not implemented yet — see TODO above.")

    yield FunctionInfo.from_fn(
        _transcribe,
        description=(
            "Transcribe an audio file to text using NVIDIA Riva/Parakeet ASR. "
            "Input is a path to the audio file; returns the transcript."
        ),
    )
