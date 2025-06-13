/*  
 logic.js – Control modular por Joystick + botones  
 Corre en el navegador móvil/PC.  
*/

(function(){
  'use strict';

  // ─── 1. WEBSOCKET + RECONEXIÓN ────────────────────────────────────
  const WS_PORT = 6671;
  const host    = window.location.hostname;
  let   ws;

  function initWS(){
    const url = 'ws://' + host + ':' + WS_PORT;
    console.log("[WS] Intentando conexión a", url);
    ws = new WebSocket(url);

    ws.onopen    = () => console.log("[WS] Conectado a", url);
    ws.onmessage = handleWS;
    ws.onerror   = err => console.error("[WS] Error:", err);
    ws.onclose   = () => {
      console.warn("[WS] Desconectado. Reintentando en 3 s…");
      setTimeout(initWS, 3000);
    };
  }
  initWS();

  // ─── 2. MENSAJES ENTRANTES ────────────────────────────────────────
  function handleWS(evt){
    let msg;
    try {
      msg = JSON.parse(evt.data);
    } catch(e){
      console.warn("[WS] JSON inválido:", evt.data);
      return;
    }
    console.log("[WS] Msg recibido:", msg);
    // (quedamos libres de getInfo para no inundar)
  }

  // ─── 3. MODOS ────────────────────────────────────────────────────
  let mode = 'walk';
  document.querySelectorAll('.mode-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      document.querySelectorAll('.mode-btn')
        .forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      mode = btn.dataset.mode;
      console.log('[MODE] Cambiado a', mode);
    });
  });

  // ─── 4. STAND / SIT / AUTONOMUS ───────────────────────────────────

  // STAND
  document.getElementById('btn-stand').addEventListener('click', ()=>{
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'posture',value:'Stand'}));
    }
    console.log('[UI] STAND enviado');
  });

  // SIT
  document.getElementById('btn-sit').addEventListener('click', ()=>{
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'posture',value:'Sit'}));
    }
    console.log('[UI] SIT enviado');
  });

  // AUTONOMUS ON/OFF
  const btnAutonomous       = document.getElementById('btn-autonomous');
  let   autonomousEnabled  = false;

  btnAutonomous.addEventListener('click', () => {
    autonomousEnabled = !autonomousEnabled;
    // Actualiza texto del botón
    btnAutonomous.textContent = `Autonomous: ${autonomousEnabled ? 'On' : 'Off'}`;
    // Envía comando WS al servidor
    if (ws.readyState === 1) {
      ws.send(JSON.stringify({
        action: 'autonomous',
        enable: autonomousEnabled
      }));
    }
    console.log('[UI] autonomous →', autonomousEnabled);
  });

  // ─── 5. MENÚS EXTRA ──────────────────────────────────────────────
  document.querySelectorAll('.extra-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const m = document.getElementById(btn.dataset.menu + '-menu');
      if(m) m.classList.add('active');
      console.log('[UI] Abrir menú', btn.dataset.menu);
    });
  });
  document.querySelectorAll('.close-btn').forEach(x=>{
    x.addEventListener('click', ()=>{
      const m = x.closest('.menu');
      if(m) m.classList.remove('active');
      console.log('[UI] Cerrar menú');
    });
  });

  // Voz: decir texto
  document.getElementById('voice-send').addEventListener('click', ()=>{
    const txt = document.getElementById('voice-text').value || '';
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'say',text:txt}));
    }
    console.log('[UI] say →', txt);
  });

  // Cambio de idioma
  document.getElementById('lang-send').addEventListener('click', ()=>{
    const lang = document.getElementById('tts-lang').value;
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'language',value:lang}));
    }
    console.log('[UI] setLanguage →', lang);
  });

  // LEDs
  document.getElementById('btn-led-set').addEventListener('click', ()=>{
    const group = document.getElementById('led-group').value;
    const hex   = document.getElementById('led-color').value;
    const r = parseInt(hex.slice(1,3),16)/255;
    const g = parseInt(hex.slice(3,5),16)/255;
    const b = parseInt(hex.slice(5,7),16)/255;
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'led',group, r, g, b}));
    }
    console.log('[UI] led-on', group, r.toFixed(2), g.toFixed(2), b.toFixed(2));
  });
  document.getElementById('btn-led-off').addEventListener('click', ()=>{
    const group = document.getElementById('led-group').value;
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'led',group, r:0, g:0, b:0}));
    }
    console.log('[UI] led-off', group);
  });

  // ─── 6. JOYSTICK ────────────────────────────────────────────────
  const base = document.querySelector('.joy-base'),
        knob = document.querySelector('.joy-knob');
  let R, Rk, LIM, vx=0, vy=0, sendI=null, active=false, touchId=null;

  function recalc(){
    R   = base.clientWidth/2;
    Rk  = knob.clientWidth/2;
    LIM = R - Rk;
  }
  window.addEventListener('load', recalc);
  window.addEventListener('resize', recalc);

  function sendCmd(){
    if(ws.readyState!==1) return;
    switch(mode){
      case 'walk':
        // ⇧ adelante = vy local; lateral = vx local
        ws.send(JSON.stringify({action:'walk',vx:vy, vy:vx, wz:0}));
        break;
      case 'larm':
        ws.send(JSON.stringify({action:'move',joint:'LShoulderPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'LShoulderRoll', value:vx}));
        break;
      case 'rarm':
        ws.send(JSON.stringify({action:'move',joint:'RShoulderPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'RShoulderRoll', value:vx}));
        break;
      case 'head':
        ws.send(JSON.stringify({action:'move',joint:'HeadPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'HeadYaw',   value:vx}));
        break;
    }
    console.log('[JOY]', mode, vx.toFixed(2), vy.toFixed(2));
  }
  function startSend(){
    if(!sendI) sendI = setInterval(sendCmd,1000/15);
  }
  function stopSend(){
    clearInterval(sendI); sendI = null;
    if(mode==='walk'){
      vx=vy=0; sendCmd();
      console.log('[JOY] walk STOP');
    } else {
      console.log('[JOY] hold position (mode=' + mode + ')');
    }
  }

  function setKnob(dx,dy){
    knob.style.transform = 'translate(-50%,-50%) translate(' + dx + 'px,'+ dy +'px)';
  }
  function centerKnob(){
    knob.style.transition = 'transform .1s';
    setKnob(0,0);
    setTimeout(function(){ knob.style.transition = ''; }, 120);
  }

  function handleMove(evt){
    if(!active) return;
    var x,y;
    if(evt.touches){
      for(var i=0;i<evt.touches.length;i++){
        if(evt.touches[i].identifier===touchId){
          x=evt.touches[i].clientX; y=evt.touches[i].clientY;
        }
      }
      if(x===undefined) return;
    } else {
      x=evt.clientX; y=evt.clientY;
    }
    var rect = base.getBoundingClientRect();
    var dx = x - rect.left - R,
        dy = y - rect.top  - R;
    var d = Math.hypot(dx,dy), f = d > LIM ? LIM/d : 1;
    dx *= f; dy *= f;
    setKnob(dx,dy);
    var nx = dx/LIM, ny = -dy/LIM;
    vx = Math.abs(nx)>0.05? nx:0;
    vy = Math.abs(ny)>0.05? ny:0;
  }

  base.addEventListener('mousedown', function(e){
    active=true; touchId=null; startSend(); handleMove(e);
  });
  window.addEventListener('mousemove', handleMove);
  window.addEventListener('mouseup', function(){
    active=false; centerKnob(); stopSend();
  });

  base.addEventListener('touchstart', function(e){
    e.preventDefault();
    active=true; touchId=e.touches[0].identifier;
    startSend(); handleMove(e);
  }, {passive:false});
  window.addEventListener('touchmove', handleMove, {passive:false});
  window.addEventListener('touchend', function(){
    active=false; centerKnob(); stopSend();
  });

  // ─── 7. (opcional) Desactivar getInfo automático
  // setInterval(function(){ if(ws.readyState===1) ws.send(JSON.stringify({action:'getInfo'})); },1000);

  // ─── 8. Enfoque para teclado ─────────────────────────────────────
  window.addEventListener('load', function(){ document.body.focus(); });

})();
