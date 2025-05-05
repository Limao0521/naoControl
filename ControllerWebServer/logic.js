/*══════════════════════════════════════════════════════════════════════
  logic.js – Joystick NES + teclado  →  WebSocket  "walk vx vy wz"
  ----------------------------------------------------------------------
  • Conecta automáticamente a ws://<host>:6671   (funciona en PC y móvil)
  • Envía los vectores a 15 Hz mientras el stick esté fuera del “dead-zone”
  • Rueda muerta (DEAD) evita ruido; watchdog del lado NAO corta en 0.6 s
  • Teclado opcional: W-A-S-D  (móvil lo ignora), D = START, E = SELECT
═══════════════════════════════════════════════════════════════════════*/

/*══════════ CONFIGURACIÓN ════════════════════════════════════════════*/
const WS_PORT = 6671;                 // puerto donde corre ws2udp.py
const SEND_HZ = 15;                   // frecuencia de envío             (Hz)
const DEAD    = 0.05;                 // radio muerto normalizado        (0-1)

/*══════════ 1. WEBSOCKET (reconexión automática) ════════════════════*/
let ws;
function openWS() {
  const host = window.location.hostname;          // ← IP/host que muestra el navegador
  ws = new WebSocket(`ws://${host}:${WS_PORT}`);

  ws.onopen  = () => console.log("[WS] Conectado");
  ws.onclose = () => { console.warn("[WS] Cerrado – reintento en 3 s");
                      setTimeout(openWS, 3000); };
  ws.onerror = err  => console.error("[WS] Error", err);
}
openWS();

/*══════════ 2. MAPEOS TECLADO OPCIONALES (START / SELECT) ═══════════*/
const keyMap = {KeyD:"start", KeyE:"select"};
const btnByKey = {};
document.querySelectorAll("button[data-key]").forEach(b=>{
  btnByKey[b.dataset.key] = b;
});
const press = b=>b?.classList.add("pressed");
const rel   = b=>b?.classList.remove("pressed");
window.addEventListener("keydown",e=>{
  const fn = keyMap[e.code]; if(!fn) return;
  press(btnByKey[e.code]);
  console.log(fn.toUpperCase());
  /* aquí puedes hacer algo útil con START/SELECT si quieres */
});
window.addEventListener("keyup",e=>rel(btnByKey[e.code]));

/*══════════ 3. JOYSTICK (touch + mouse) ═════════════════════════════*/
(function initJoystick(){
  const base = document.querySelector(".joy-base");
  const knob = document.querySelector(".joy-knob");

  let R=0, Rk=0, LIM=0;               // radios px
  function recalc() {                 // recalcula en resize / load
    R   = base.clientWidth / 2;
    Rk  = knob.clientWidth / 2;
    LIM = R - Rk;
  }
  window.addEventListener("load",   recalc);
  window.addEventListener("resize", recalc);

  let active=false, id=null, vx=0, vy=0, timer=null;

  const sendWalk = () =>{
    if(ws.readyState!==1) return;     // OPEN = 1
    ws.send(`walk ${vx.toFixed(2)} ${vy.toFixed(2)} 0`);
  };
  const startSend = ()=>{
    if(timer) return;
    timer = setInterval(sendWalk, 1000/SEND_HZ);
  };
  const stopSend = ()=>{
    if(!timer) return;
    clearInterval(timer); timer=null;
    vx=vy=0; sendWalk();              // manda un 0 0 0 para frenar
  };

  const setKnob = (dx,dy)=>
    knob.style.transform = `translate(-50%,-50%) translate(${dx}px,${dy}px)`;

  const center = ()=>{
    knob.style.transition="transform .1s";
    setKnob(0,0);
    setTimeout(()=>knob.style.transition="",120);
  };

  const onMove = e =>{
    if(!active) return;
    const p = e.touches
            ? [...e.touches].find(t=>t.identifier===id) : e;
    if(!p) return;

    const rect = base.getBoundingClientRect();
    const x = p.clientX - rect.left - R;
    const y = p.clientY - rect.top  - R;

    const d  = Math.hypot(x,y);
    const f  = d > LIM ? LIM/d : 1;          // clamp
    const dx = x*f, dy = y*f;
    setKnob(dx,dy);

    const nx =  dx / LIM;   // derecha +
    const ny = -dy / LIM;   // adelante +
    if(Math.hypot(nx,ny) < DEAD){ vx=vy=0; return; }
    vx = ny; vy = nx;        // frame NAO: vx=adelante+, vy=izquierda+
  };

  function start(e){
    recalc();                              // asegura valores válidos
    active=true; id = e.touches ? e.touches[0].identifier : null;
    startSend(); onMove(e);
  }
  const end = ()=>{ active=false; center(); stopSend(); };

  base.addEventListener("mousedown",start);
  base.addEventListener("touchstart",e=>{e.preventDefault();start(e);});
  window.addEventListener("mousemove",onMove);
  window.addEventListener("touchmove",onMove,{passive:false});
  window.addEventListener("mouseup", end);
  window.addEventListener("touchend",end);
  window.addEventListener("touchcancel",end);
})();

/*══════════ 4. TECLADO WASD PARA PC (opcional) ═════════════════════*/
const axisKeys = {KeyW:[ 1,0], KeyS:[-1,0], KeyA:[0,1], KeyD:[0,-1]};
let keyVx=0, keyVy=0;
const sendKeyWalk = ()=>ws.readyState===1 &&
                      ws.send(`walk ${keyVx} ${keyVy} 0`);
window.addEventListener("keydown",e=>{
  if(axisKeys[e.code]){
    const [vx,vy]=axisKeys[e.code];
    keyVx=vx; keyVy=vy; sendKeyWalk();
  }
});
window.addEventListener("keyup",e=>{
  if(axisKeys[e.code]){ keyVx=keyVy=0; sendKeyWalk(); }
});

/*══════════ 5. Foco para que reciba teclado inmediatamente ═════════*/
window.addEventListener("load",()=>document.body.focus());
