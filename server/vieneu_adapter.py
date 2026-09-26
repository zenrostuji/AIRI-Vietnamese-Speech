from __future__ import annotations

import inspect


class VieNeuAdapter:
    # Compatibility layer: if a future VieNeu SDK changes its constructor,
    # only this adapter needs adjustment.
    def __init__(self):
        from vieneu import Vieneu  # type: ignore[import-untyped]
        # This application targets predictable local CPU execution. Forcing ONNX
        # avoids probing CUDA and prevents heavyweight GPU backends from loading.
        self.engine = Vieneu(mode="v3turbo", device="cpu", backend="onnx", precision="int8")

        # Detect infer() signature once at startup — avoids repeated
        # try/except waterfall on every synthesize call.
        sig = inspect.signature(self.engine.infer)
        params = set(sig.parameters)
        self._infer_has_style = "style" in params
        self._infer_has_speed = "speed" in params
        self._infer_positional = list(sig.parameters.keys())

    def synthesize(self, text: str, voice: str, style: str = "tu_nhien", speed: float = 1.0):
        kwargs: dict = {"text": text, "voice": voice}
        if self._infer_has_style:
            kwargs["style"] = style
        if self._infer_has_speed:
            kwargs["speed"] = speed
        audio = self.engine.infer(**kwargs)
        # v3 turbo currently accepts **kwargs but does not implement speed. Keep
        # OpenAI's speed contract by time-stretching only when the SDK cannot.
        if not self._infer_has_speed and abs(speed - 1.0) > 0.01:
            import numpy as np
            samples = np.asarray(audio, dtype=np.float32).squeeze()
            if samples.size == 0:
                return samples
            new_length = max(1, int(len(samples) / float(speed)))
            old_x = np.linspace(0.0, 1.0, len(samples), endpoint=False)
            new_x = np.linspace(0.0, 1.0, new_length, endpoint=False)
            audio = np.interp(new_x, old_x, samples).astype(np.float32)
        return audio

    def add_voice(self, name: str, wav_path: str):
        try:
            return self.engine.add_voice(name, wav_path, denoise=True, save=False)
        except ModuleNotFoundError as exc:
            if exc.name == "torch":
                raise RuntimeError(
                    "Voice cloning needs PyTorch. Close the app, then run "
                    "start-ui.bat again so it can install the CPU runtime."
                ) from exc
            raise

    def save_voices(self, path: str):
        return self.engine.save_voices(path)

    def remove_voice(self, name: str):
        fn = getattr(self.engine, "remove_voice", None)
        if fn:
            return fn(name, save=False)
