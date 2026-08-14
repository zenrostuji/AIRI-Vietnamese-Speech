from __future__ import annotations

class VieNeuAdapter:
    # Compatibility layer: if a future VieNeu SDK changes its constructor,
    # only this adapter needs adjustment.
    def __init__(self):
        from vieneu import Vieneu
        self.engine = Vieneu(mode="v3turbo")

    def synthesize(self, text, voice, style="tu_nhien", speed=1.0):
        try:
            return self.engine.infer(
                text=text, voice=voice, style=style
            )
        except TypeError:
            try:
                return self.engine.infer(text=text, voice=voice)
            except TypeError:
                return self.engine.infer(text, voice)

    def add_voice(self, name, wav_path):
        try:
            return self.engine.add_voice(
                name, wav_path, denoise=True, save=False
            )
        except ModuleNotFoundError as exc:
            if exc.name == "torch":
                raise RuntimeError(
                    "Voice cloning needs PyTorch. Close the app, then run "
                    "start-ui.bat again so it can install the CPU runtime."
                ) from exc
            raise

    def save_voices(self, path):
        return self.engine.save_voices(path)

    def remove_voice(self, name):
        fn = getattr(self.engine, "remove_voice", None)
        if fn:
            return fn(name, save=False)
