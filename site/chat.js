/* Заказы и чат с продавцом на сайте. Ссылка из бота открывает сайт с ?order=ID. */
(function(){
var ST={pending:"ждёт проверки",confirmed:"оплачен, ждём выдачу",completed:"завершён",rejected:"отклонён",cancelled:"отменён"};
var T=null,LAST=0,OID=0,ROLE="buyer";
function E(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function box(){var d=document.getElementById("oc");if(!d){d=document.createElement("div");d.id="oc";document.body.appendChild(d)}d.className="on";return d}
function need(){if(typeof authed==="function"&&authed())return false;try{toast("Сначала войди через Telegram")}catch(e){}if(window.openCodeLogin)openCodeLogin();return true}
window.closeOrders=function(){clearInterval(T);T=null;var d=document.getElementById("oc");if(d)d.remove()};
window.openOrders=function(){
 if(need())return;
 var d=box();d.innerHTML='<div class="bx"><button class="x" onclick="closeOrders()" aria-label="Закрыть">✕</button><h3>Мои заказы</h3><div id="ol"><p>Загрузка…</p></div></div>';
 api("/api/orders").then(function(r){
  var l=document.getElementById("ol");if(!l)return;
  if(!r.ok){l.innerHTML='<p>'+E(r.error||"Не получилось")+'</p>';return}
  l.innerHTML=r.orders.length?r.orders.map(function(o){
   var act='';
   if(o.delivered&&o.status=="confirmed")act='<button class="sm" onclick="confirmOrder('+o.id+')">Получил</button>';
   else if(o.status=="completed"&&!o.reviewed)act='<button class="sm" onclick="openReviewForm('+o.id+')">Отзыв</button>';
   return '<div class="orow"><div><b>№'+o.id+' · '+E(o.name)+'</b><span>'+o.price+' ₽ · '+E(o.delivered&&o.status=="confirmed"?"выдан, подтверди получение":(ST[o.status]||o.status))+'</span></div><div class="oa">'+act+'<button class="sm" onclick="openOrderChat('+o.id+')">Чат</button></div></div>'}).join(""):'<p>Заказов пока нет</p>'
 }).catch(function(){var l=document.getElementById("ol");if(l)l.innerHTML="<p>Сервер недоступен</p>"})
};
function draw(msgs,role,reset){
 var m=document.getElementById("ocm");if(!m)return;
 if(reset)m.innerHTML="";
 msgs.forEach(function(x){
  var mine=(x.from==role);
  var b=document.createElement("div");b.className="mg "+(mine?"me":"ot");
  b.innerHTML=E(x.text).replace(/\n/g,"<br>")+'<small>'+(x.from=="seller"?"Продавец":"Покупатель")+'</small>';
  m.appendChild(b);LAST=Math.max(LAST,x.id)});
 if(msgs.length)m.scrollTop=m.scrollHeight;
 var e=document.getElementById("ocn");if(e&&reset&&!m.children.length)e.style.display="";else if(e)e.style.display="none"
}
function poll(reset){
 api("/api/chat/"+OID+"?after="+(reset?0:LAST)).then(function(r){
  if(!r.ok){if(reset){var m=document.getElementById("ocm");if(m)m.innerHTML='<p>'+E(r.error||"Не получилось")+'</p>'}return}
  ROLE=r.role;
  var h=document.getElementById("och");if(h)h.textContent="Заказ №"+r.order.id+" · "+r.order.name;
  var s=document.getElementById("ocs");if(s)s.textContent=(r.order.delivered&&r.order.status=="confirmed")?"выдан":(ST[r.order.status]||r.order.status);
  draw(r.messages,r.role,reset)
 }).catch(function(){})
}
window.openOrderChat=function(oid){
 if(need())return;
 clearInterval(T);OID=oid;LAST=0;
 var d=box();
 d.innerHTML='<div class="bx ch"><button class="x" onclick="closeOrders()" aria-label="Закрыть">✕</button><h3 id="och">Заказ №'+oid+'</h3><div class="st" id="ocs"></div><div id="ocm" class="cm"></div><p id="ocn" style="display:none">Сообщений пока нет. Напиши продавцу, он ответит здесь, а уведомление придёт в Telegram.</p><div class="cr"><textarea id="oct" rows="1" maxlength="1000" placeholder="Сообщение"></textarea><button class="go" id="ocb">➤</button></div></div>';
 var t=document.getElementById("oct"),b=document.getElementById("ocb");
 function send(){var v=t.value.trim();if(!v||b.disabled)return;b.disabled=true;
  api("/api/chat/"+OID,{text:v}).then(function(r){b.disabled=false;if(!r.ok)return toast(r.error||"Не отправилось");t.value="";poll(false)}).catch(function(){b.disabled=false;toast("Сервер недоступен")})}
 b.onclick=send;t.onkeydown=function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
 poll(true);T=setInterval(function(){poll(false)},4000)
};

/* ---- подтверждение получения и отзыв ---- */
window.confirmOrder=function(oid){
 api("/api/orders/"+oid+"/done",{}).then(function(r){
  if(!r.ok)return toast(r.error||"Не получилось");
  toast("Заказ закрыт, спасибо!");openReviewForm(oid)}).catch(function(){toast("Сервер недоступен")})
};
window.openReviewForm=function(oid){
 var d=box();
 d.innerHTML='<div class="bx"><button class="x" onclick="closeOrders()" aria-label="Закрыть">✕</button><h3>Отзыв по заказу №'+oid+'</h3><p>Напиши пару слов о покупке. Отзыв увидят другие покупатели.</p><textarea id="rvt" rows="5" maxlength="800" style="width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08);color:inherit;padding:10px 12px;font:inherit"></textarea><div class="er" id="rve" style="min-height:18px;color:#ff7b7b;font-size:13px;margin:6px 0"></div><button class="sm" id="rvb" style="width:100%;padding:13px">Отправить отзыв</button><button class="lk" onclick="openOrders()" style="display:block;margin:10px auto 0;background:none;border:0;color:inherit;opacity:.7;font-size:13px">Позже</button></div>';
 var b=document.getElementById("rvb");
 b.onclick=function(){var t=document.getElementById("rvt").value.trim();if(b.disabled)return;b.disabled=true;
  api("/api/orders/"+oid+"/review",{text:t}).then(function(r){b.disabled=false;
   if(!r.ok){document.getElementById("rve").textContent=r.error||"Не получилось";return}
   toast("Спасибо за отзыв!",2400);openReviews()}).catch(function(){b.disabled=false;document.getElementById("rve").textContent="Сервер недоступен"})}
};
/* ---- отзывы на сайте ---- */
window.openReviews=function(){
 var d=box();
 d.innerHTML='<div class="bx"><button class="x" onclick="closeOrders()" aria-label="Закрыть">✕</button><h3>Отзывы</h3><div id="rvl"><p>Загрузка…</p></div><a href="https://t.me/PhonkerOt" target="_blank" rel="noopener" class="sm" style="display:block;text-align:center;text-decoration:none;margin-top:10px;padding:12px">Все отзывы в канале</a></div>';
 fetch((window.API||"")+"/api/reviews").then(function(x){return x.json()}).then(function(r){
  var l=document.getElementById("rvl");if(!l)return;
  l.innerHTML=(r.ok&&r.reviews.length)?r.reviews.map(function(v){
   return '<div class="orow" style="display:block"><b>'+E(v.user)+' · '+E(v.product)+'</b><span style="display:inline;margin-left:6px">'+E(v.at)+'</span><p style="margin:6px 0 0;opacity:1">'+E(v.text).replace(/\n/g,"<br>")+'</p>'+(v.photo?'<img src="'+(window.API||"")+'/api/review_photo/'+v.id+'" alt="" loading="lazy" style="max-width:100%;border-radius:12px;margin-top:8px">':'')+'</div>'}).join(""):'<p>Отзывов пока нет</p>'
 }).catch(function(){var l=document.getElementById("rvl");if(l)l.innerHTML="<p>Сервер недоступен</p>"})
};
/* ---- вкладки админа: чаты, люди, оплата ---- */
window.aCh=function(){adm_("chats").then(function(r){
 $("abody").innerHTML=r.chats.length?r.chats.map(function(x){
  return '<div class="arow"><div><b>'+(x.from=="buyer"?"🟢 ":"↩️ ")+'№'+x.order+' · '+E(x.name)+'</b><span>'+(x.username?'@'+E(x.username):'id '+x.user)+' · '+E(x.text)+'</span></div><button class="sm" onclick="openOrderChat('+x.order+')">Чат</button></div>'}).join(""):'<p class="empty">Чатов пока нет</p>'}).catch(function(){})};
window.aUs=function(q){adm_("users",{q:q||""}).then(function(r){var s=r.stats;
 $("abody").innerHTML='<div class="kpi">'+[[s.total,"Всего"],[s.new_24h,"Новых за 24 ч"],[s.new_7d,"Новых за 7 дн"],[s.active_24h,"Активных за 24 ч"],[s.active_7d,"Активных за 7 дн"]].map(function(x){return '<div><b>'+x[0]+'</b><span>'+x[1]+'</span></div>'}).join("")+'</div>'+
 '<div class="arow"><input class="inp" id="usq" placeholder="@username или id" value="'+E(q||"")+'" style="flex:1"><button class="sm pri" onclick="aUs(document.getElementById(\'usq\').value)">Найти</button></div>'+
 (r.searched?(r.found?'<div class="arow"><div><b>'+(r.found.username?'@'+E(r.found.username):'без username')+'</b><span>id '+r.found.id+'</span></div></div>':'<p class="empty">Не найден</p>'):'')}).catch(function(){})};
window.aPay=function(){adm_("pay_get").then(function(r){
 $("abody").innerHTML='<div class="arow"><div><b>Оплата звёздами Telegram</b><span>'+(r.stars?"включена":"выключена")+'</span></div><button class="sm pri" onclick="adm_(\'pay_toggle\').then(aPay)">'+(r.stars?"Выключить":"Включить")+'</button></div>'}).catch(function(){})};

/* кнопки "Заказы" и "Мои заказы" открывают заказы на сайте */
function hook(){["ord","ordtab"].forEach(function(id){var a=document.getElementById(id);if(!a)return;
 a.style.display="";a.removeAttribute("target");a.setAttribute("href","#");
 a.addEventListener("click",function(e){e.preventDefault();e.stopImmediatePropagation();openOrders()},true)})}
/* ссылка из бота: ?order=ID */
function deep(){
 var m=/[?&]order=(\d+)/.exec(location.search);if(!m)return;
 var oid=parseInt(m[1],10),n=0,asked=false;
 var iv=setInterval(function(){n++;
  if(typeof authed==="function"&&authed()){clearInterval(iv);try{history.replaceState(null,"",location.pathname)}catch(e){}openOrderChat(oid)}
  else if(n>=3&&!asked){asked=true;if(window.openCodeLogin)openCodeLogin()}
  else if(n>600)clearInterval(iv)},1000)
}
window.addEventListener("load",function(){hook();deep()});
})();
