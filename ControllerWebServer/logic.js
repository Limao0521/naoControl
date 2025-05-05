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
    ws = new WebSocket(`ws://${host}:${WS_PORT}`);
    ws.onopen    = () => console.log(`[WS] Conectado a ${host}:${WS_PORT}`);
    ws.onmessage = handleWS;
    ws.onclose   = () => {
      console.warn('[WS] Desconectado. Reintentando en 3s…');
      setTimeout(initWS, 3000);
    };
    ws.onerror   = err => console.error('[WS] Error', err);
  }
  initWS();

  // ─── 2. MENSAJES ENTRANTES (getInfo) ─────────────────────────────
  function handleWS(evt){
    let msg;
    try {
      msg = JSON.parse(evt.data);
    } catch(e){
      console.warn('[WS] JSON inválido:', evt.data);
      return;
    }
    if(!msg.info) return;

    // IP y batería
    const ipElem   = document.getElementById('stat-ip');
    const battElem = document.getElementById('stat-batt');
    if(ipElem)   ipElem.textContent   = host;
    if(battElem) battElem.textContent = msg.info.battery;

    // Articulaciones
    const tbody = document.querySelector('#stat-joints tbody');
    if(tbody){
      tbody.innerHTML = '';
      for(const [j,st] of Object.entries(msg.info.joints)){
        const row = `<tr>
          <td>${j}</td>
          <td>${st.pos.toFixed(2)}</td>
          <td>${st.temp.toFixed(1)}</td>
        </tr>`;
        tbody.insertAdjacentHTML('beforeend', row);
      }
    }

    console.log('[WS] Stats actualizadas');
  }

  // ─── 3. MODOS: walk | larm | rarm | head ─────────────────────────
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

  // ─── 4. STAND / SIT (caminar vs sentarse) ────────────────────────
  document.getElementById('btn-stand')?.addEventListener('click', ()=>{
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'posture',value:'Stand'}));
    }
    console.log('[UI] STAND enviado');
  });
  document.getElementById('btn-sit')?.addEventListener('click', ()=>{
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'posture',value:'Sit'}));
    }
    console.log('[UI] SIT enviado');
  });

  // ─── 5. MENÚS EXTRA (voz, cámara, leds, stats) ──────────────────
  document.querySelectorAll('.extra-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const m = document.getElementById(btn.dataset.menu + '-menu');
      m?.classList.add('active');
      console.log('[UI] Abrir menú', btn.dataset.menu);
    });
  });
  document.querySelectorAll('.close-btn').forEach(x=>{
    x.addEventListener('click', ()=>{
      x.closest('.menu')?.classList.remove('active');
      console.log('[UI] Cerrar menú');
    });
  });

  // Voz
  document.getElementById('voice-send')?.addEventListener('click', ()=>{
    const txt = document.getElementById('voice-text')?.value || '';
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'say',text:txt}));
    }
    console.log('[UI] say →', txt);
  });

// LEDs – multiselección de grupos
document.getElementById('btn-led-set').addEventListener('click', ()=>{
  // Array de grupos seleccionados
  const groups = Array.from(
    document.querySelectorAll('input.led-checkbox:checked')
  ).map(cb => cb.value);
  if(groups.length === 0) {
    console.warn('[UI] ningún grupo LED seleccionado');
    return;
  }
  // Color hex → [0..1]
  const hex = document.getElementById('led-color').value;
  const r = parseInt(hex.slice(1,3),16)/255;
  const g = parseInt(hex.slice(3,5),16)/255;
  const b = parseInt(hex.slice(5,7),16)/255;
  if(ws.readyState === 1) {
    ws.send(JSON.stringify({action:'led', groups, r, g, b}));
  }
  console.log('[UI] led-on', groups, r.toFixed(2), g.toFixed(2), b.toFixed(2));
});

document.getElementById('btn-led-off').addEventListener('click', ()=>{
  const groups = Array.from(
    document.querySelectorAll('input.led-checkbox:checked')
  ).map(cb => cb.value);
  if(groups.length === 0) {
    console.warn('[UI] ningún grupo LED seleccionado');
    return;
  }
  if(ws.readyState === 1) {
    ws.send(JSON.stringify({action:'led', groups, r:0, g:0, b:0}));
  }
  console.log('[UI] led-off', groups);
});


  // ─── 6. JOYSTICK – CALCULO vx,vy + envío periódico ─────────────
  const base = document.querySelector('.joy-base'),
        knob = document.querySelector('.joy-knob');
  let R, Rk, LIM;
  let vx=0, vy=0, sendI=null, active=false, touchId=null;

  // recalc radios
  function recalc(){
    R   = base.clientWidth / 2;
    Rk  = knob.clientWidth / 2;
    LIM = R - Rk;
  }
  window.addEventListener('load', recalc);
  window.addEventListener('resize', recalc);

  // envío según modo
  function sendCmd(){
    if(ws.readyState!==1) return;
    switch(mode){
      case 'walk':
        ws.send(JSON.stringify({action:'walk',vx,vy,wz:0}));
        break;
      case 'larm':
        ws.send(JSON.stringify({action:'move',joint:'LShoulderPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'LShoulderRoll',value:vx}));
        break;
      case 'rarm':
        ws.send(JSON.stringify({action:'move',joint:'RShoulderPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'RShoulderRoll',value:vx}));
        break;
      case 'head':
        ws.send(JSON.stringify({action:'move',joint:'HeadPitch',value:vy}));
        ws.send(JSON.stringify({action:'move',joint:'HeadYaw',value:vx}));
        break;
    }
    console.log('[JOY]', mode, vx.toFixed(2), vy.toFixed(2));
  }

  function startSend(){
    if(!sendI) sendI = setInterval(sendCmd, 1000/15);
  }
  function stopSend(){
    clearInterval(sendI);
    sendI = null;
    // sólo enviamos stop en walk; en move mantenemos última posición
    if(mode==='walk'){
      vx=vy=0;
      sendCmd();
      console.log('[JOY] walk STOP');
    } else {
      console.log('[JOY] hold position (mode=', mode, ')');
    }
  }

  // mueve el knob
  function setKnob(dx,dy){
    knob.style.transform = `translate(-50%,-50%) translate(${dx}px,${dy}px)`;
  }
  function centerKnob(){
    knob.style.transition = 'transform .1s';
    setKnob(0,0);
    setTimeout(()=> knob.style.transition = '', 120);
  }

  // handle move
  function handleMove(evt){
    if(!active) return;
    let x, y;
    if(evt.touches){
      const t = [...evt.touches].find(t=>t.identifier===touchId);
      if(!t) return;
      x = t.clientX; y = t.clientY;
    } else {
      x = evt.clientX; y = evt.clientY;
    }
    const rect = base.getBoundingClientRect();
    let dx = x - rect.left - R;
    let dy = y - rect.top  - R;
    const d = Math.hypot(dx,dy), f = d > LIM ? LIM/d : 1;
    dx *= f; dy *= f;
    setKnob(dx,dy);

    const nx = dx / LIM;   // + derecha, - izquierda
    const ny = -dy / LIM;  // + adelante, - atrás
    vx = Math.abs(nx) > 0.05 ? nx : 0;
    vy = Math.abs(ny) > 0.05 ? ny : 0;
  }

  // start / end events
  base.addEventListener('mousedown', e=>{
    active = true; touchId = null;
    startSend(); handleMove(e);
  });
  window.addEventListener('mousemove', handleMove);
  window.addEventListener('mouseup', ()=>{
    active = false; centerKnob(); stopSend();
  });

  base.addEventListener('touchstart', e=>{
    e.preventDefault();
    active = true;
    touchId = e.touches[0].identifier;
    startSend(); handleMove(e);
  }, {passive:false});
  window.addEventListener('touchmove', handleMove, {passive:false});
  window.addEventListener('touchend', ()=>{
    active = false; centerKnob(); stopSend();
  });

  // ─── 7. PETICIONES DE ESTADO cada 1s ────────────────────────────
  setInterval(()=>{
    if(ws.readyState===1){
      ws.send(JSON.stringify({action:'getInfo'}));
      console.log('[UI] getInfo');
    }
  }, 1000);

  // ─── 8. Enfoque para teclado (opcional) ─────────────────────────
  window.addEventListener('load', ()=> document.body.focus());

})();
