# J.A.R.V.I.S. — Asistente personal por voz

> Asistente de voz en español rioplatense, con cerebro híbrido (Gemini en la nube + Ollama local), 19 herramientas y una interfaz visual estilo Iron Man. Hecho en Python como proyecto de aprendizaje de robótica e IA.

![Interfaz de JARVIS](docs/interfaz.png)

## ✨ Qué hace

- 🎙️ **Manos libres:** lo llamás por su nombre ("ey Jarvis"), charlan y con "chau Jarvis" vuelve a dormir.
- 🧠 **Cerebro híbrido:** usa Gemini cuando hay internet y cupo gratis; si no, sigue funcionando 100 % local con Ollama.
- 🛠️ **19 herramientas** (*tool calling*):

| Área | Herramientas |
|---|---|
| Información | Google Noticias, Wikipedia, resumen de PDFs, consulta de planillas Excel/CSV |
| Datos al instante | Hora, clima (Open-Meteo), dólar (DolarApi), calculadora exacta |
| Productividad | Notas, recordatorios, pomodoro |
| Control de la PC | Volumen, música, YouTube, capturas, abrir programas y sitios, bloqueo (con confirmación) |

- 🖥️ **Interfaz visual:** reactor animado que reacciona a tu voz y a la de JARVIS, registro del sistema y datos en vivo.
- 🎩 **Personalidad:** mayordomo británico con humor seco, saludo con parte del día, sonidos y efecto de voz.

## 🏗️ Arquitectura

```
 Micrófono ─► Whisper (oído) ─► cerebro.py ─► Piper (voz) ─► Parlante
                                   │
                    ┌──────────────┴──────────────┐
              Gemini (nube)                 Ollama (local)
                    └──────────────┬──────────────┘
                            herramientas.py
              ┌──────────────┬─────┴──────┬───────────────┐
         control_pc.py  informacion.py  APIs web     notas / timers

 interfaz.py: ventana (hilo principal) ◄── cola de avisos ◄── JARVIS (otro hilo)
```

| Archivo | Responsabilidad |
|---|---|
| `jarvis_wake.py` | Programa principal manos libres: detección del nombre, modo conversación, arranque |
| `interfaz.py` | Interfaz visual (tkinter) conectada por hilos y una cola de mensajes |
| `cerebro.py` | Enrutador de cerebros: Gemini con respaldo en Ollama |
| `gemini.py` | Conexión con Gemini: orden de modelos y manejo de la cuota gratis |
| `herramientas.py` | Registro de herramientas y bucle de *tool calling* para Ollama |
| `control_pc.py` | Herramientas de control de Windows |
| `informacion.py` | Búsqueda de noticias, PDFs y planillas (solo en carpetas permitidas) |
| `personalidad.py` | Personalidad, frases y saludo de arranque |
| `efectos.py` | Sonidos sintetizados y efecto de voz |
| `jarvis_voz.py` | Oído y voz (Whisper + Piper) |
| `jarvis_chat.py` | Versión por texto |
| `lanzador.py` / `JARVIS.bat` | Panel de botones para abrir todo |

## 🚀 Instalación (Windows)

Requisitos: Python 3.13, [Ollama](https://ollama.com) y Git.

```powershell
git clone https://github.com/TU_USUARIO/jarvis.git
cd jarvis
py install 3.13
pymanager exec -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

ollama pull llama3.2:3b
python -m piper.download_voices es_AR-daniela-high

copy .env.example .env   # y poné tu clave de Gemini (gratis)
```

## ▶️ Uso

```powershell
python interfaz.py       # JARVIS con interfaz visual
python jarvis_wake.py    # manos libres, solo consola
python cerebro.py        # probar el cerebro por texto
```

O hacé doble clic en `JARVIS.bat`.

Ejemplos: *"Jarvis, ¿qué hora es?"* · *"Subí el volumen"* · *"¿Cómo salió Talleres?"* · *"Resumime el apunte de Materiales"* · *"¿Cuánto gasté este mes?"*

## 🔒 Seguridad y privacidad

- Listas blancas: JARVIS solo abre programas y sitios aprobados, y solo lee archivos de carpetas permitidas.
- Nunca usa `eval`: la calculadora evalúa expresiones con `ast`.
- Las acciones delicadas (bloquear la PC) piden confirmación **en el código**, no dependen del modelo.
- La clave vive en `.env`, que nunca se sube al repositorio.
- Con la cuota gratis de Gemini, Google puede usar lo que se le envía. Para documentos privados, `USAR_GEMINI_EN_ARCHIVOS = False` procesa todo en local.

## 🗺️ Próximos pasos

- [ ] Pruebas automáticas (pytest) e integración continua (GitHub Actions)
- [ ] Configuración centralizada y memoria entre sesiones
- [ ] Interfaz web
- [ ] Control de un brazo robótico de 6 ejes con ESP32

## 📄 Licencia

[MIT](LICENSE)
