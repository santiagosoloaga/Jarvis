import faulthandler
import time
faulthandler.enable()
print("1) Importando librerias...", flush=True)
from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel
print("2) Descargando el modelo...", flush=True)
ruta = snapshot_download("Systran/faster-whisper-base")
print("   Descargado en:", ruta, flush=True)
print("3) Cargando el modelo en memoria...", flush=True)
inicio = time.time()
modelo = WhisperModel(ruta, device="cpu", compute_type="int8")
print(f"4) WHISPER OK ({time.time() - inicio:.1f} s)", flush=True)
