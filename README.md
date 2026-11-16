# J.A.R.V.I.S. — Asistente personal por voz

> Asistente de voz en español rioplatense, con cerebro híbrido (Gemini en la nube + Ollama local), 23 herramientas y una interfaz visual estilo Iron Man. Hecho en Python como proyecto de aprendizaje de robótica e IA.

![Interfaz de JARVIS](docs/interfaz.png)

## ✨ Qué hace

- 🎙️ **Manos libres:** lo llamás por su nombre ("ey Jarvis"), charlan y con "chau Jarvis" vuelve a dormir.
- 🧠 **Cerebro híbrido:** usa Gemini cuando hay internet y cupo gratis; si no, sigue funcionando 100 % local con Ollama.
- 🛠️ **23 herramientas** (*tool calling*):

| Área | Herramientas |
|---|---|
| Información | Google Noticias, Wikipedia, resumen de PDFs, consulta de planillas Excel/CSV |
| Datos al instante | Hora, clima (Open-Meteo), dólar (DolarApi), calculadora exacta |
| Productividad | Notas, recordatorios, pomodoro, Google Calendar (agendar y consultar), tracker de hábitos en Notion (marcar y consultar) |
| Control de la PC | Volumen, música, YouTube, capturas, abrir programas y sitios, bloqueo (con confirmación) |

- ⚡ **Atajos locales:** los pedidos de todos los días (hora, hábitos, abrir apps, volumen, música) se resuelven sin Gemini, casi al instante.
- 🗣️ **Voz:** Piper local por defecto; opcionalmente voz humana en la nube con Gemini TTS (con respaldo automático en Piper).
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
| `calendario.py` | Google Calendar: agendar y consultar eventos (las fechas las calcula Python) |
| `habitos.py` | Tracker de hábitos en Notion (Habit Quest): marcar lo cumplido y consultar qué falta |
| `atajos.py` | Respuestas rápidas sin Gemini para los pedidos más repetidos |
| `voz_nube.py` | Voz opcional con Gemini TTS; si falla o se acaba la cuota, usa Piper |
| `informacion.py` | Búsqueda de noticias, PDFs y planillas (solo en carpetas permitidas) |
| `personalidad.py` | Personalidad, frases y saludo de arranque |
| `efectos.py` | Sonidos sintetizados y efecto de voz |
| `jarvis_voz.py` | Oído y voz (Whisper + Piper) |
| `jarvis_chat.py` | Versión por texto |
| `lanzador.py` / `JARVIS.bat` | Panel de botones para abrir todo |
| `pruebas/` | Scripts de prueba y diagnóstico (voces, TTS, micrófono) |

## 🚀 Instalación (Windows)

Requisitos: Python 3.13, [Ollama](https://ollama.com) y Git.

```powershell
git clone https://github.com/santiagosoloaga/Jarvis.git
cd Jarvis
py install 3.13
pymanager exec -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

ollama pull llama3.2:3b
ollama pull qwen3:4b      # solo para jarvis_chat.py (modo "calculá")
python -m piper.download_voices es_AR-daniela-high

copy .env.example .env   # y poné tu clave de Gemini (gratis)
```

### 📅 Google Calendar (opcional)

1. En [Google Cloud Console](https://console.cloud.google.com/) creá un proyecto y habilitá la **Google Calendar API**.
2. Configurá la pantalla de consentimiento OAuth (tipo *Externo*, en modo prueba) y agregate como usuario de prueba.
3. Creá una credencial **ID de cliente OAuth → App de escritorio**, descargá el JSON y guardalo como `credentials.json` en la carpeta del proyecto.
4. Corré `python calendario.py` una vez: se abre el navegador, aceptás y se guarda `token.json`.

`credentials.json` y `token.json` están en `.gitignore`: son la llave de tu calendario y **nunca** se suben. JARVIS solo pide el permiso `calendar.events` (ver y editar eventos).

### 📓 Hábitos en Notion (opcional)

1. En [notion.so/profile/integrations](https://www.notion.so/profile/integrations) creá una integración **interna** y copiá su secreto.
2. Ponelo en tu `.env` como `NOTION_TOKEN=...`.
3. En Notion, abrí la página del tracker → **···** → **Conexiones** → agregá tu integración.
4. Probá con `python habitos.py`. Por voz: *"marcá que fui al gimnasio"*, *"¿qué me falta hoy?"*.

Los IDs de tus bases están al comienzo de `habitos.py`.

### 🗣️ Voz y velocidad

- `MOTOR_VOZ` en `jarvis_voz.py`: `"piper"` (local, rápido, sin cuota) o `"gemini"` (más humana, usa la cuota gratis de Gemini; si se agota vuelve sola a Piper).
- `DETECTAR_INGLES` en `jarvis_voz.py`: `False` = siempre español (más rápido); `True` = también entiende frases enteras en inglés (más lento).
- `ATAJOS_ACTIVOS` en `atajos.py`: apaga los atajos locales y manda todo a Gemini.
- La terminal imprime `[tiempos]` por cada pedido (oído, cerebro, voz) para medir dónde se va el tiempo.

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
- Con la cuota gratis de Gemini, Google puede usar lo que se le envía. Por eso tus PDFs y planillas se procesan **en local por defecto** (`USAR_GEMINI_EN_ARCHIVOS = False` en `informacion.py`).
- Bloquear la PC exige que confirmes en un mensaje nuevo: el modelo no puede preguntar y confirmar solo en el mismo turno.

## 🗺️ Próximos pasos

- [ ] Pruebas automáticas (pytest) e integración continua (GitHub Actions)
- [ ] Bot de Telegram para usar JARVIS desde el celular
- [ ] Configuración centralizada y memoria entre sesiones
- [ ] Interfaz web
- [ ] Control de un brazo robótico de 6 ejes con ESP32

## 📄 Licencia

[MIT](LICENSE)
