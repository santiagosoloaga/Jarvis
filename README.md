# JARVIS

Asistente personal por voz, 100% local. Proyecto de aprendizaje con Mentor.

## Programas

| Archivo | Qué hace |
| --- | --- |
| `jarvis_chat.py` | Chat por texto: memoria, comandos (/hora, /reset, /ayuda) y enrutador de modelos |
| `jarvis_voz.py` | JARVIS por voz: Whisper (oído) + Ollama (cerebro) + Piper (boca), con Enter |
| `jarvis_wake.py` | JARVIS manos libres: "Hey Jarvis" + acciones (hora, clima, programas, recordatorios) |
| `herramientas.py` | Las herramientas de JARVIS (tool calling). `python herramientas.py` las prueba por texto |
| `control_pc.py` | Herramientas para la compu: volumen, música, YouTube, capturas y bloqueo (con confirmación) |
| `cerebro.py` | Cerebro híbrido: Gemini (nube) con respaldo en Ollama (local). Necesita `GEMINI_API_KEY` en `.env` |
| `lanzador.py` / `JARVIS.bat` | Panel de botones para abrir todo sin escribir comandos |
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
