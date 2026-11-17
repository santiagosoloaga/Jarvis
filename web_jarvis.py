# web_jarvis.py - JARVIS en tu celular, como pagina web.
#
# Tu PC sigue siendo el cerebro (atajos + Gemini/Ollama + las herramientas).
# Este programa levanta una pagina; la abris desde el celu y escribis o
# hablas. Lo que pidas (volumen, abrir apps, habitos, capturas...) pasa en TU PC.
#
# Seguridad (por capas):
#   1. Solo escucha en 127.0.0.1: nadie en tu WiFi lo ve.
#   2. Tailscale lo publica SOLO a tus dispositivos (tailscale serve).
#   3. Pide una clave (JARVIS_WEB_CLAVE en .env) en cada pedido.
#
# Puesta en marcha: mira la seccion "JARVIS en el celular" del README.
# No usa librerias nuevas (http.server de Python).

import hmac
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

import atajos
import cerebro
import control_pc
import herramientas
from personalidad import PERSONALIDAD

load_dotenv()

# ---------- CONFIGURACION ----------
PUERTO = int(os.environ.get("JARVIS_WEB_PUERTO", "8765"))
CLAVE = os.environ.get("JARVIS_WEB_CLAVE", "").strip()
MAX_MENSAJES = 20            # historial que recuerda en la charla
MAX_AUDIO = 15 * 1024 * 1024  # 15 MB por nota de voz
USAR_ATAJOS = True

_oido = None                 # Whisper se carga con la primera nota de voz
_candado = threading.Lock()  # el cerebro atiende de a un pedido
_avisos = []                 # recordatorios/pomodoro pendientes de mostrar


def nuevo_historial():
    return [{"role": "system", "content": PERSONALIDAD + herramientas.INSTRUCCIONES}]


historial = nuevo_historial()


# ---------- Cerebro (mismo recorrido que en la PC) ----------
def responder(texto):
    """Devuelve (respuesta, ruta_de_captura_o_None)."""
    with _candado:
        herramientas.ultima_accion = "ninguna"
        historial.append({"role": "user", "content": texto})
        respuesta = None
        if USAR_ATAJOS:
            rapida = atajos.responder_rapido(texto)
            if rapida is not None:
                nombre, respuesta = rapida
                herramientas.ultima_accion = nombre
                print(f"  [herramienta] {nombre} (atajo, sin Gemini)")
        if respuesta is None:
            try:
                respuesta = cerebro.pensar(historial)
            except Exception as error:
                historial.pop()
                print("  [error]", error)
                return "Tuve un problema pensando eso. Probá de nuevo en un momento.", None
        historial.append({"role": "assistant", "content": respuesta})
        del historial[1:-MAX_MENSAJES]
        foto = None
        if herramientas.ultima_accion == "captura_de_pantalla":
            capturas = sorted(control_pc.CARPETA_CAPTURAS.glob("captura_*.png"))
            foto = capturas[-1].name if capturas else None
        return respuesta, foto


def transcribir_audio(datos):
    global _oido
    from faster_whisper import WhisperModel

    import jarvis_voz
    if _oido is None:
        print("  [oído] cargando Whisper para notas de voz...")
        _oido = WhisperModel(jarvis_voz.MODELO_WHISPER, device="cpu", compute_type="int8",
                             cpu_threads=min(8, os.cpu_count() or 4))
    # El celu manda audio crudo (16 bits, 16 kHz, mono): no hace falta 'av' ni ffmpeg.
    import numpy as np
    if len(datos) % 2:
        datos = datos[:-1]
    audio = np.frombuffer(datos, dtype=np.int16).astype(np.float32) / 32768.0
    return jarvis_voz.transcribir(_oido, audio)


# ---------- Pagina ----------
PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b1220"><title>JARVIS</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e6f1ff;font:16px system-ui,sans-serif;
display:flex;flex-direction:column;height:100dvh}
header{padding:12px 16px;border-bottom:1px solid #1d2b45;display:flex;justify-content:space-between;align-items:center}
header b{color:#4fd1ff;letter-spacing:3px}header span button{margin-left:8px}
#chat{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
.m{max-width:85%;padding:10px 14px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word}
.yo{align-self:flex-end;background:#1b4b7a}.j{align-self:flex-start;background:#16233b}
.av{align-self:center;background:#4a3b12;font-size:14px}
.m img{max-width:100%;border-radius:8px;margin-top:6px}
form{display:flex;gap:8px;padding:10px;border-top:1px solid #1d2b45;padding-bottom:max(10px,env(safe-area-inset-bottom))}
input{flex:1;padding:12px;border-radius:22px;border:1px solid #1d2b45;background:#101a2e;color:#e6f1ff;font-size:16px}
button{border:0;border-radius:22px;padding:12px 16px;background:#4fd1ff;color:#06101f;font-size:16px;font-weight:600}
button.sec{background:#16233b;color:#e6f1ff;padding:6px 10px;font-size:14px}
#mic.grab{background:#ff5d5d;color:#fff}
</style></head><body>
<header><b>JARVIS</b><span><button class="sec" id="voz">🔇</button><button class="sec" id="reset">Borrar charla</button></span></header>
<div id="chat"></div>
<form id="f"><input id="t" placeholder="Escribile a JARVIS..." autocomplete="off">
<button type="button" id="mic">🎙️</button><button>➤</button></form>
<script>
const $=id=>document.getElementById(id),chat=$('chat');
let clave=localStorage.getItem('jarvis_clave')||'',hablar=localStorage.getItem('jarvis_voz')==='1';
$('voz').textContent=hablar?'🔊':'🔇';
function pedirClave(){clave=prompt('Clave de JARVIS:')||'';localStorage.setItem('jarvis_clave',clave);}
function burbuja(txt,cls,foto){const d=document.createElement('div');d.className='m '+cls;d.textContent=txt;
 if(foto){const i=document.createElement('img');i.src='/captura?n='+encodeURIComponent(foto)+'&k='+encodeURIComponent(clave);d.appendChild(i);}
 chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
function decir(t){if(!hablar||!window.speechSynthesis)return;speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(t);u.lang='es-AR';speechSynthesis.speak(u);}
async function api(ruta,opts={}){if(!clave)pedirClave();
 opts.headers=Object.assign({'X-Clave':clave},opts.headers||{});
 let r=await fetch(ruta,opts);
 if(r.status===401){pedirClave();opts.headers['X-Clave']=clave;r=await fetch(ruta,opts);}
 if(!r.ok)throw new Error(r.status===401?'Clave incorrecta':'Error '+r.status);return r.json();}
async function enviar(texto){burbuja(texto,'yo');const p=burbuja('…','j');
 try{const r=await api('/chat',{method:'POST',body:JSON.stringify({texto})});
  p.remove();burbuja(r.respuesta,'j',r.foto);decir(r.respuesta);}
 catch(e){p.textContent='⚠️ '+e.message;}}
$('f').onsubmit=e=>{e.preventDefault();const t=$('t').value.trim();if(!t)return;$('t').value='';enviar(t);};
$('voz').onclick=()=>{hablar=!hablar;localStorage.setItem('jarvis_voz',hablar?'1':'0');$('voz').textContent=hablar?'🔊':'🔇';};
$('reset').onclick=async()=>{try{await api('/reset',{method:'POST',body:'{}'});chat.innerHTML='';}catch(e){burbuja('⚠️ '+e.message,'j');}};
let rec=null,trozos=[];
$('mic').onclick=async()=>{
 if(rec){rec.stop();return;}
 if(!navigator.mediaDevices){burbuja('⚠️ El micrófono necesita HTTPS (mirá el README: tailscale serve).','j');return;}
 try{const s=await navigator.mediaDevices.getUserMedia({audio:true});
  rec=new MediaRecorder(s);trozos=[];$('mic').classList.add('grab');$('mic').textContent='⏹';
  rec.ondataavailable=e=>trozos.push(e.data);
  rec.onstop=async()=>{s.getTracks().forEach(x=>x.stop());$('mic').classList.remove('grab');$('mic').textContent='🎙️';
   const blob=new Blob(trozos,{type:rec.mimeType});rec=null;const p=burbuja('🎙️ escuchando…','j');
   let pcm;try{const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const aud=await ctx.decodeAudioData(await blob.arrayBuffer());ctx.close();
    const off=new OfflineAudioContext(1,Math.max(1,Math.ceil(aud.duration*16000)),16000);
    const fuente=off.createBufferSource();fuente.buffer=aud;fuente.connect(off.destination);fuente.start();
    const f=(await off.startRendering()).getChannelData(0),i16=new Int16Array(f.length);
    for(let i=0;i<f.length;i++)i16[i]=Math.max(-1,Math.min(1,f[i]))*32767;pcm=i16;}
   catch(e){p.textContent='⚠️ No pude procesar el audio: '+e.message;return;}
   try{const r=await api('/voz',{method:'POST',body:pcm,headers:{'Content-Type':'application/octet-stream'}});
    p.remove();if(r.texto)burbuja(r.texto,'yo');burbuja(r.respuesta,'j',r.foto);decir(r.respuesta);}
   catch(e){p.textContent='⚠️ '+e.message;}};
  rec.start();}catch(e){burbuja('⚠️ No pude usar el micrófono: '+e.message,'j');}};
setInterval(async()=>{if(!clave)return;try{const r=await fetch('/avisos',{headers:{'X-Clave':clave}});
 if(r.ok){const l=await r.json();l.forEach(a=>{burbuja('🔔 '+a,'av');decir(a);});}}catch(e){}},5000);
burbuja('A sus órdenes, señor.','j');
</script></body></html>"""


# ---------- Servidor ----------
class Manejador(BaseHTTPRequestHandler):
    def log_message(self, formato, *args):      # sin ruido en la consola
        pass

    def _responder(self, codigo, cuerpo, tipo="application/json"):
        if not isinstance(cuerpo, bytes):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + ("; charset=utf-8" if "text" in tipo or "json" in tipo else ""))
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _autorizado(self, consulta=None):
        dada = self.headers.get("X-Clave") or (consulta or {}).get("k", [""])[0]
        ok = hmac.compare_digest(dada.encode(), CLAVE.encode())
        if not ok:
            time.sleep(1)                       # frena los intentos a fuerza bruta
            self._responder(401, {"error": "clave"})
        return ok

    def do_GET(self):
        url = urlparse(self.path)
        consulta = parse_qs(url.query)
        if url.path == "/":
            self._responder(200, PAGINA.encode("utf-8"), "text/html")
        elif url.path == "/avisos":
            if self._autorizado():
                with _candado:
                    pendientes = list(_avisos)
                    _avisos.clear()
                self._responder(200, pendientes)
        elif url.path == "/captura":
            if not self._autorizado(consulta):
                return
            nombre = consulta.get("n", [""])[0]
            ruta = control_pc.CARPETA_CAPTURAS / nombre
            if re.fullmatch(r"captura_[\d\-_]+\.png", nombre) and ruta.is_file():
                self._responder(200, ruta.read_bytes(), "image/png")
            else:
                self._responder(404, {"error": "no existe"})
        else:
            self._responder(404, {"error": "no existe"})

    def do_POST(self):
        if not self._autorizado():
            return
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_AUDIO:
            self._responder(413, {"error": "muy grande"})
            return
        cuerpo = self.rfile.read(largo)
        try:
            if self.path == "/chat":
                texto = str(json.loads(cuerpo or b"{}").get("texto", "")).strip()
                if not texto:
                    self._responder(400, {"error": "vacío"})
                    return
                print(f"Vos (celu): {texto}")
                respuesta, foto = responder(texto)
                print("JARVIS:", respuesta)
                self._responder(200, {"respuesta": respuesta, "foto": foto})
            elif self.path == "/voz":
                texto = transcribir_audio(cuerpo)
                if not texto:
                    self._responder(200, {"texto": "", "respuesta": "No te entendí, señor. ¿Puede repetirlo?"})
                    return
                print(f"Vos (celu, voz): {texto}")
                respuesta, foto = responder(texto)
                print("JARVIS:", respuesta)
                self._responder(200, {"texto": texto, "respuesta": respuesta, "foto": foto})
            elif self.path == "/reset":
                with _candado:
                    historial[:] = nuevo_historial()
                self._responder(200, {"ok": True})
            else:
                self._responder(404, {"error": "no existe"})
        except Exception as error:               # un pedido roto no tumba el servidor
            print("  [error]", error)
            self._responder(500, {"error": "falló"})


def main():
    if len(CLAVE) < 6:
        print("Falta JARVIS_WEB_CLAVE en .env (mínimo 6 caracteres). Mirá el README.")
        return
    # Los recordatorios y el pomodoro también llegan a la pagina del celu
    previo = herramientas.avisar
    herramientas.avisar = lambda texto: (previo(texto), _avisos.append(texto))
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"JARVIS web listo en http://127.0.0.1:{PUERTO}  (Ctrl+C para apagar)")
    print(f"Para el celu:  tailscale serve --bg {PUERTO}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nJARVIS web apagado.")


if __name__ == "__main__":
    main()
