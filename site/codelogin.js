/* Вход через Telegram: @username -> бот присылает код в Telegram -> вводишь код. Код создаёт сервер, придумать его нельзя. */
(function(){
function box(){return document.getElementById("cl")}
function post(p,b){return fetch((window.API||"")+p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)}).then(function(x){return x.json()})}
var rid="";
function render(step,err){
 var d=box();if(!d){d=document.createElement("div");d.id="cl";document.body.appendChild(d)}
 d.className="on";
 var h='<div class="bx"><button class="x" aria-label="Закрыть" onclick="closeCodeLogin()">✕</button><h3>Вход через Telegram</h3>';
 if(step==1){
  h+='<p>Введи свой Telegram username. Бот пришлёт тебе код. Сначала нажми Start в нашем боте с этого аккаунта.</p><input class="inp" id="cl_u" maxlength="33" autocapitalize="off" spellcheck="false" placeholder="@username">'
}else{
  h+='<p>Мы отправили код в Telegram. Он действует 5 минут. Код создаёт только бот, придумать его нельзя. Никому его не сообщай.</p><input class="inp" id="cl_c" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="6 цифр">'
}
 h+='<div class="er" id="cl_e">'+(err||"")+'</div><button class="go" id="cl_b">'+(step==1?"Получить код":"Войти")+'</button>';
 if(step==2)h+='<button class="lk" onclick="openCodeLogin()">Запросить новый код</button>';
 h+='</div>';d.innerHTML=h;
 var b=document.getElementById("cl_b"),inp=document.getElementById(step==1?"cl_u":"cl_c");
 inp.focus();inp.onkeydown=function(e){if(e.key==="Enter")b.click()};
 b.onclick=function(){
  if(b.disabled)return;b.disabled=true;
  if(step==1){
   var u=inp.value.trim();
   if(!/^@?[A-Za-z][A-Za-z0-9_]{4,31}$/.test(u)){b.disabled=false;return err1("Username: 5-32 символа, латиница, цифры и _")}
   post("/api/login/code/request",{username:u}).then(function(r){b.disabled=false;
    if(!r.ok){err1(r.error||"Не получилось");if(r.bot_url)addBot(r.bot_url);return}rid=r.rid;render(2)}).catch(function(){b.disabled=false;err1("Сервер недоступен")})
  }else{
   var c=inp.value.trim();
   if(!/^\d{6}$/.test(c)){b.disabled=false;return err1("Код состоит из 6 цифр")}
   post("/api/login/code/verify",{rid:rid,code:c}).then(function(r){b.disabled=false;
    if(!r.ok)return err1(r.error||"Не получилось");
    SESS=r.session;try{localStorage.setItem("ps",SESS)}catch(e){}
    closeCodeLogin();if(typeof gClose==="function"){GCL=true;try{gClose()}catch(e){}}
    setUser(r.user);loadMe();toast("Ты вошёл как "+r.user.first_name,2200)}).catch(function(){b.disabled=false;err1("Сервер недоступен")})
  }}
};
function addBot(u){var e=document.getElementById("cl_e");if(!e||document.getElementById("cl_bot"))return;var a=document.createElement("a");a.id="cl_bot";a.href=u;a.target="_blank";a.rel="noopener";a.className="go";a.style.cssText="display:block;text-align:center;text-decoration:none;margin:0 0 8px";a.textContent="Открыть бота и нажать Start";e.after(a)}
function err1(t){var e=document.getElementById("cl_e");if(e)e.textContent=t}
window.openCodeLogin=function(){try{panel()}catch(e){}render(1)};
window.openBotPrompt=function(u){
 if(!u||document.getElementById("cl"))return;
 var d=document.createElement("div");d.id="cl";d.className="on";
 d.innerHTML='<div class="bx"><button class="x" aria-label="Закрыть" onclick="closeCodeLogin()">✕</button><h3>Заказ оплачен</h3><p>Детали заказа и чат с продавцом в нашем Telegram-боте. Открой его, чтобы получить товар.</p><a class="go" href="'+u+'" target="_blank" rel="noopener" style="display:block;text-align:center;text-decoration:none" onclick="closeCodeLogin()">Перейти в бота</a></div>';
 document.body.appendChild(d)};
window.closeCodeLogin=function(){var d=box();if(d)d.remove()};
})();
