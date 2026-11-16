# JARVIS

Asistente personal por voz, 100% local. Proyecto de aprendizaje con Mentor.

## Programas

| Archivo | Qué hace |
| --- | --- |
| `jarvis_chat.py` | Chat por texto: memoria, comandos (/hora, /reset, /ayuda) y enrutador de modelos |
| `jarvis_voz.py` | JARVIS por voz: Whisper (oído) + Ollama (cerebro) + Piper (boca), con Enter |
| `jarvis_wake.py` | JARVIS manos libres: se despierta cuando decís "Hey Jarvis" |
| `pruebas/` | Scripts de prueba de cada parte por separado |

## Cómo armarlo en una compu nueva

```powershell
py install 3.13
pymanager exec -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull llama3.2:3b
ollama pull qwen3:4b
python -m piper.download_voices es_AR-daniela-high
```
