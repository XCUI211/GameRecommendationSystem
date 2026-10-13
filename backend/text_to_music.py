"""Real local MusicGen inference; optional ML dependencies load on demand."""
import io
import wave
from functools import lru_cache


@lru_cache(maxsize=2)
def _load_model(model_name, device):
    from transformers import AutoProcessor, MusicgenForConditionalGeneration

    processor = AutoProcessor.from_pretrained(model_name)
    model = MusicgenForConditionalGeneration.from_pretrained(model_name).to(device)
    model.eval()
    return processor, model


def generate_local_music(prompt, duration=8, model_name="facebook/musicgen-small", device=None):
    """Return WAV bytes and an error; never replace failed AI output with fake music."""
    try:
        import numpy as np
        import torch
        import transformers
    except ImportError:
        return None, (
            "Local MusicGen requires torch, transformers and scipy. "
            "Install requirements-music.txt (Python 3.11 or 3.12 recommended), "
            "or configure MUSIC_BACKEND=hf and HF_MUSIC_ENDPOINT."
        )
    try:
        duration = max(1, min(30, int(duration)))
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if "/" not in model_name:
            model_name = f"facebook/musicgen-{model_name}"
        processor, model = _load_model(model_name, device)
        inputs = processor(text=[prompt], padding=True, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        frame_rate = getattr(model.config.audio_encoder, "frame_rate", 50)
        with torch.inference_mode():
            audio = model.generate(**inputs, max_new_tokens=int(duration * frame_rate))
        audio = audio[0].detach().cpu().float().numpy()
        if audio.ndim == 1:
            audio = audio[np.newaxis, :]
        if audio.ndim != 2 or audio.shape[1] == 0:
            raise ValueError("MusicGen returned an invalid audio tensor.")
        pcm = (np.clip(audio, -1, 1).T * 32767).astype("<i2")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(audio.shape[0])
            wav.setsampwidth(2)
            wav.setframerate(model.config.audio_encoder.sampling_rate)
            wav.writeframes(pcm.tobytes())
        return output.getvalue(), None
    except Exception as exc:
        return None, f"MusicGen generation failed: {exc}"
