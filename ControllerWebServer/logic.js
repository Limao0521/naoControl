/*========== 1. PLACEHOLDERS ==========*/
const noop=()=>{};
function moveUp()   {noop();console.log("UP");}
function moveDown() {noop();console.log("DOWN");}
function moveLeft() {noop();console.log("LEFT");}
function moveRight(){noop();console.log("RIGHT");}
function btnA()     {noop();console.log("A");}
function btnB()     {noop();console.log("B");}
function start()    {noop();console.log("START");}
function select()   {noop();console.log("SELECT");}

/*========== 2. MAPA tecla → acción ==========*/
const keyMap = {
    ArrowUp: "moveUp",       
    ArrowDown: "moveDown",   
    ArrowLeft: "moveLeft",   
    ArrowRight: "moveRight",
    
    KeyD: "start",           // START con ‘D’
    KeyC: "select",          // SELECT con ‘E’
  
    KeyA: "btnA",            // A con la tecla A física
    KeyB: "btnB",            // B con la tecla B física
    Space: "btnA",           // (extra) barra espaciadora = A
    KeyJ: "btnB",            // (extra) J = B
    Enter: "start"           // (extra) ENTER = START
  };

/*========== 3. Hash tecla → botón DOM ==========*/
const btnByKey={};
document.querySelectorAll("button[data-key]").forEach(b=>{
  btnByKey[b.dataset.key]=b;
});

/*========== 4. Funciones de feedback ==========*/
const addPress = btn=>{
  if(!btn) return;
  btn.classList.add("pressed");
};
const removePress = btn=>{
  if(!btn) return;
  btn.classList.remove("pressed");
};

/*========== 5. Eventos de teclado ==========*/
window.addEventListener("keydown",e=>{
  const fnName=keyMap[e.code];
  if(fnName && typeof window[fnName]==="function"){
    window[fnName]();
    addPress(btnByKey[e.code]);
  }
});
window.addEventListener("keyup",e=>removePress(btnByKey[e.code]));

/*========== 6. Eventos táctiles / ratón ==========*/
document.querySelectorAll("button[data-action]").forEach(btn=>{
  const fnName=btn.dataset.action;
  const fire=()=>{
    if(typeof window[fnName]==="function") window[fnName]();
    addPress(btn);
    setTimeout(()=>removePress(btn),120);
  };
  btn.addEventListener("touchstart",e=>{e.preventDefault();fire();});
  btn.addEventListener("mousedown",fire);
});

/*========== 7. Foco automático para teclado ==========*/
window.addEventListener("load",()=>document.body.focus());
