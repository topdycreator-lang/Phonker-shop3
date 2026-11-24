var BOT=""; // ← ссылка на бота магазина
var $=function(i){return document.getElementById(i)};
var IC={home:'<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',grid:'<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>',chat:'<path d="M4 5h16v11H9l-5 4z"/>',faq:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',cart:'<path d="M3 4h2l2.2 11h11l2-8H6.5"/><circle cx="9" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>',sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',moon:'<path d="M20 14A8 8 0 1 1 10 4a6 6 0 0 0 10 10z"/>'};
function icons(){document.querySelectorAll("i[data-ic]").forEach(function(e){e.innerHTML='<svg viewBox="0 0 24 24">'+IC[e.dataset.ic]+'</svg>'})}
icons();

/* ---- Chromium: включаем преломление стекла ---- */
(function(){var ua=navigator.userAgent;if(/Chrome|YaBrowser|Edg/.test(ua)&&!/Firefox/.test(ua)){document.documentElement.classList.add("cr");
 var m='<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><defs><linearGradient id="x" x1="0" x2="1"><stop offset="0" stop-color="#000"/><stop offset=".22" stop-color="#800000"/><stop offset=".78" stop-color="#800000"/><stop offset="1" stop-color="#f00"/></linearGradient><linearGradient id="y" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000"/><stop offset=".22" stop-color="#000080"/><stop offset=".78" stop-color="#000080"/><stop offset="1" stop-color="#00f"/></linearGradient></defs><rect width="400" height="400" fill="url(#x)"/><rect width="400" height="400" fill="url(#y)" style="mix-blend-mode:screen"/></svg>';
 $("map").setAttribute("href","data:image/svg+xml;charset=utf-8,"+encodeURIComponent(m))}})();

/* ---- Тема ---- */
function setTheme(t){document.documentElement.dataset.theme=t;$("ti").dataset.ic=t=="dark"?"sun":"moon";icons();try{localStorage.setItem("pt",t)}catch(e){}pal()}
function theme(){setTheme(document.documentElement.dataset.theme=="dark"?"light":"dark")}
var st0;try{st0=localStorage.getItem("pt")}catch(e){}

/* ---- Фон: псевдо-3D в стиле PS1 (низкое разрешение, flat-shading, дрожание вершин) ---- */
var cv=$("c"),g=cv.getContext("2d"),W,H,S=4,px=0,py=0,tx=0,ty=0,P;
var BASE={dark:[[30,200,110],[14,120,70],[255,210,63],[70,230,150]],light:[[90,215,160],[150,235,190],[255,215,90],[60,190,130]]};
function pal(){P=BASE[document.documentElement.dataset.theme]}
function rs(){W=cv.width=Math.ceil(innerWidth/S);H=cv.height=Math.ceil(innerHeight/S)}
var SH={oct:{v:[[1,0,0],[-1,0,0],[0,1.5,0],[0,-1.5,0],[0,0,1],[0,0,-1]],f:[[2,0,4],[2,4,1],[2,1,5],[2,5,0],[3,4,0],[3,1,4],[3,5,1],[3,0,5]]},
 cube:{v:[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],f:[[0,1,2,3],[5,4,7,6],[4,0,3,7],[1,5,6,2],[3,2,6,7],[4,5,1,0]]},
 tet:{v:[[1,1,1],[-1,-1,1],[-1,1,-1],[1,-1,-1]],f:[[0,1,2],[0,3,1],[0,2,3],[1,3,2]]}};
var OB=[],i,k=["oct","cube","tet","oct","oct","cube"];
for(i=0;i<20;i++)OB.push({s:SH[k[i%6]],x:(Math.random()-.5)*22,y:(Math.random()-.5)*13,z:7+Math.random()*17,sc:.5+Math.random()*.9,a:Math.random()*6,b:Math.random()*6,va:(Math.random()-.5)*.8,vb:(Math.random()-.5)*.8,c:i%5==0?2:i%2,ph:Math.random()*6});
var L=[-.4,.7,-.6],ll=Math.hypot(L[0],L[1],L[2]);L=L.map(function(v){return v/ll});
function frame(t){t=t/1000;px+=(tx-px)*.05;py+=(ty-py)*.05;g.clearRect(0,0,W,H);
 var cx=W/2+px*W*.06,cy=H/2+py*H*.06,f=W*.95,F=[],dk=document.documentElement.dataset.theme=="dark";
 OB.forEach(function(o){var A=o.a+t*o.va,B=o.b+t*o.vb,ca=Math.cos(A),sa=Math.sin(A),cb=Math.cos(B),sb=Math.sin(B),oy=o.y+Math.sin(t*.6+o.ph)*.7;
  var V=o.s.v.map(function(p){var X=p[0]*o.sc,Y=p[1]*o.sc,Z=p[2]*o.sc,x1=X*ca+Z*sa,z1=-X*sa+Z*ca,y1=Y*cb-z1*sb,z2=Y*sb+z1*cb;return[x1+o.x-px*2,y1+oy,z2+o.z]});
  o.s.f.forEach(function(fc){var a=V[fc[0]],b=V[fc[1]],c=V[fc[2]],u=[b[0]-a[0],b[1]-a[1],b[2]-a[2]],w=[c[0]-a[0],c[1]-a[1],c[2]-a[2]],
   n=[u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]],nl=Math.hypot(n[0],n[1],n[2])||1;n=[n[0]/nl,n[1]/nl,n[2]/nl];
   var m=[0,0,0];fc.forEach(function(j){m[0]+=V[j][0];m[1]+=V[j][1];m[2]+=V[j][2]});m=m.map(function(v){return v/fc.length});
   var oc=[o.x-px*2,oy,o.z];if(n[0]*(m[0]-oc[0])+n[1]*(m[1]-oc[1])+n[2]*(m[2]-oc[2])<0)n=[-n[0],-n[1],-n[2]];
   if(n[0]*m[0]+n[1]*m[1]+n[2]*m[2]>=0)return;
   var d=Math.max(0,n[0]*L[0]+n[1]*L[1]+n[2]*L[2]),I=.32+.68*d,col=P[o.c];
   F.push({z:m[2],c:"rgb("+Math.min(255,col[0]*I*(dk?1:1.1)|0)+","+Math.min(255,col[1]*I*(dk?1:1.1)|0)+","+Math.min(255,col[2]*I*(dk?1:1.1)|0)+")",p:fc.map(function(j){return[Math.round(cx+V[j][0]*f/V[j][2]),Math.round(cy-V[j][1]*f/V[j][2])]})})})});
 F.sort(function(a,b){return b.z-a.z});g.globalAlpha=dk?.9:.8;
 F.forEach(function(q){g.fillStyle=q.c;g.beginPath();q.p.forEach(function(p,j){j?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1])});g.closePath();g.fill()});
 if(!RM)requestAnimationFrame(frame)}
var RM=matchMedia("(prefers-reduced-motion:reduce)").matches;
addEventListener("resize",rs);
addEventListener("pointermove",function(e){tx=e.clientX/innerWidth-.5;ty=e.clientY/innerHeight-.5});
addEventListener("deviceorientation",function(e){if(e.gamma!=null){tx=Math.max(-.5,Math.min(.5,e.gamma/60));ty=Math.max(-.5,Math.min(.5,(e.beta-45)/90))}});
addEventListener("scroll",function(){ty=Math.max(-.5,Math.min(.5,scrollY/3000-.2))},{passive:true});
setTheme(st0||(matchMedia("(prefers-color-scheme:light)").matches?"light":"dark"));rs();if(!RM)requestAnimationFrame(frame);

/* ---- Профиль из Telegram (мини-приложение) + вход через бота в браузере ---- */
var API=window.PHONKER_API||"";/* адрес сервера бота; пусто = тот же домен, с которого открыт сайт */
var tg=window.Telegram&&Telegram.WebApp,U=tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user,INIT=tg&&tg.initData||"",SESS="";
try{SESS=localStorage.getItem("ps")||""}catch(e){}
if(tg&&U){try{tg.ready();tg.expand()}catch(e){}}
function authH(){return INIT?{"Authorization":"tma "+INIT}:(SESS?{"Authorization":"Bearer "+SESS}:{})}
function api(path,body){var o={headers:authH()};if(body!==undefined){o.method="POST";o.headers["Content-Type"]="application/json";o.body=JSON.stringify(body)}
 return fetch(API+path,o).then(function(r){return r.json().catch(function(){return{ok:false,error:"Ошибка сервера"}})})}
function setUser(u){U=u;var nm=U?(U.first_name+(U.last_name?" "+U.last_name:"")):"Гость";if(!nm.trim())nm="Пользователь";
 ["av1","av2"].forEach(function(id){var a=$(id);if(U&&U.photo_url){a.style.backgroundImage='url("'+U.photo_url+'")';a.textContent=""}else{a.style.backgroundImage="";a.textContent=nm.charAt(0).toUpperCase()}});
 $("nm1").textContent=nm;$("nm2").textContent=nm;
 $("un2").textContent=U?(U.username?"@"+U.username:"без username"):"Войди через Telegram";
 $("id2").textContent=U?"ID: "+U.id+(LOGIN?" · "+LOGIN:""):"";$("loginpw").style.display=U?"none":"";
 $("login").style.display=U?"none":"";$("ord").href=BOT||"#";$("ordtab").href=BOT||"#";$("ord").style.display="";$("ordtab").style.display=""}
setUser(U);
function loadMe(){if(!INIT&&!SESS)return;api("/api/me").then(function(r){if(r.ok){LOGIN=r.login||"";REGD=!!r.registered;setUser(r.user);ISADM=!!r.is_admin;$("admbtn").style.display=ISADM?"":"none";if(!REGD)gShow("reg",!INIT);else{askWrite();if($("gate").classList.contains("on")){GCL=true;gClose()}}}else if(!INIT){SESS="";try{localStorage.removeItem("ps")}catch(e){}}})}
loadMe();
var LT=0,ISADM=false,LOGIN="",REGD=false;
/* Бот может написать человеку только с его разрешения. Просим один раз, если Telegram его ещё не дал. */
/* Покупать можно только с аккаунтом: без него открываем экран, где надо зарегистрироваться или войти */
function needAcc(){if(REGD)return false;panel();gShow("reg",!INIT);$("ghint").textContent="Чтобы покупать, нужен аккаунт: зарегистрируйся или войди.";return true}
function askWrite(){try{var u=tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user;if(INIT&&u&&u.allows_write_to_pm===false&&tg.requestWriteAccess)tg.requestWriteAccess()}catch(e){}}
function login(){if(U)return false;openCodeLogin();return false}

/* ---- Каталог ---- */
/* IM (иконки игр) объявлен в images.js, он подключается раньше этого файла */
var G={bs:{n:"Brawl Stars",d:"Гемы, пассы, особые акции",c:"linear-gradient(145deg,#ffcf2e,#e67e12)",s:"bs",cats:{"Пассы":[["Pass Case","Откройте кейс и получите Brawl Pass, Brawl Pass Plus или Pro Pass. Шансы равные: по 33,3% на каждый",359],["Brawl Pass","Обычный Brawl Pass",299],["Brawl Pass Plus","Brawl Pass Plus",349],["Pro Pass","Pro Pass",549],["Brawl Pass Plus x8","8 штук",1499]],"Гемы":[["Гемы x33","33 гема",100],["Гемы x88","88 гемов",149],["Гемы x187","187 гемов",289],["Гемы x396","396 гемов",399],["Гемы x1045","1045 гемов",799],["Гемы x2200","2200 гемов",1349]],"Особые акции":[["Синий Френк","Особая акция",2199],["Красный Френк","Особая акция",2199],["Оба Френка","Особая акция",3999]]}},
cr:{n:"Clash Royale",d:"Гемы и Pass Royale",c:"linear-gradient(145deg,#4a7bff,#b3262f)",s:"cr",cats:{"Гемы":[["Гемы x500","500 гемов",199],["Гемы x1200","1200 гемов",249],["Гемы x2500","2500 гемов",349],["Гемы x6500","6500 гемов",749],["Гемы x14000","14000 гемов",1299],["Гемы x42000","42000 гемов",2799]],"Пассы":[["Pass Royale","Pass Royale",349],["Pass Royale x8","8 штук",1499]]}},
coc:{n:"Clash of Clans",d:"Гемы и золотой пропуск",c:"linear-gradient(145deg,#7a3fd1,#e0a21a)",s:"coc",cats:{"Гемы":[["Гемы x500","500 гемов",199],["Гемы x1200","1200 гемов",249],["Гемы x2500","2500 гемов",349],["Гемы x6500","6500 гемов",749],["Гемы x14000","14000 гемов",1299],["Гемы x42000","42000 гемов",2799]],"Золотой пропуск":[["Золотой пропуск","Gold Pass",249],["Золотой пропуск x8","8 штук",1199]]}}};
var HIT=['bs|Pass Case','bs|Brawl Pass Plus','cr|Pass Royale','coc|Золотой пропуск'];
var C={},cur,tab,METHODS=null;try{C=JSON.parse(sessionStorage.getItem("pc")||"{}")}catch(e){}
Object.keys(C).forEach(function(k){if(!C[k].pid)delete C[k]});
/* актуальные товары и цены берём у бота: id нужен для оплаты */
function loadShop(){
 fetch(API+"/api/catalog").then(function(r){return r.json()}).then(function(r){if(!r.ok)return;
  Object.keys(r.catalog).forEach(function(g){if(G[g])G[g].cats=r.catalog[g]});
  Object.keys(C).forEach(function(k){var g=k.split("|")[0],t=k.split("|")[1],n=k.split("|")[2],f=null;
   var arr=G[g]&&G[g].cats[t];if(arr)arr.forEach(function(p){if(p[3]===C[k].pid){f=p}});if(!f){delete C[k]}else C[k].p=f[2]});
  sv();upd();if(cur){if(!G[cur].cats[tab])tab=Object.keys(G[cur].cats)[0];draw()}}).catch(function(){});
 fetch(API+"/api/config").then(function(r){return r.json()}).then(function(r){if(!r.ok)return;if(r.bot){BOT=r.bot;setUser(U)}METHODS=r.methods;if(r.notice&&r.notice.on){var nb=$("chn");nb.innerHTML="📢 "+r.notice.text.replace(/^📢\s*/,"").replace(/[<>&]/g,"")+(r.notice.url?' <a href="'+r.notice.url+'" target="_blank" rel="noopener">Перейти в канал</a>':"");nb.style.display=""}
  if(r.methods.length){$("pay").innerHTML=r.methods.map(function(m,i){return '<label><input type="radio" name="p" value="'+m.id+'"'+(i?'':' checked')+'><div>'+m.label+'<small>'+(m.id=="stars"?'Работает в любой стране, оплата внутри Telegram':/СБП/i.test(m.label)?'Оплата в приложении любого банка РФ':'Оплата на сайте')+'</small></div></label>'}).join("")}
  setUser(U)}).catch(function(){})}
function sv(){try{sessionStorage.setItem("pc",JSON.stringify(C))}catch(e){}}
$("gamesBox").innerHTML=Object.keys(G).map(function(k){var q=G[k];return '<button class="game glass" onclick="openG(\''+k+'\')"><div class="ico"><img src="'+IM[q.s]+'" alt="'+q.n+'"></div><h3>'+q.n+'</h3><p>'+q.d+'</p><span class="go">→</span></button>'}).join("");
function openG(k){cur=k;tab=Object.keys(G[k].cats)[0];$("gt").innerHTML='<span class="gt-ico"><img src="'+IM[G[k].s]+'" alt=""></span>'+G[k].n;$("shop").classList.add("on");draw();$("shop").scrollIntoView({behavior:"smooth"})}
function bn(g,t){openG(g);tab=t;draw()}
function home(){$("shop").classList.remove("on");$("games").scrollIntoView({behavior:"smooth"})}
function draw(){var cs=G[cur].cats;
 $("tabs").innerHTML=Object.keys(cs).map(function(t){return '<button class="tab'+(t==tab?' on':'')+'" onclick="tab=\''+t+'\';draw()">'+t+'</button>'}).join("");
 $("grid").innerHTML=cs[tab].map(function(p,i){return '<div class="item glass">'+(HIT.indexOf(cur+'|'+p[0])>-1?'<span class="hit">ХИТ 🔥</span>':'')+'<h4>'+p[0]+'</h4><p>'+p[1]+'</p><div class="price">'+p[2]+' <small>₽</small></div><button class="add" onclick="add('+i+')">В корзину</button></div>'}).join("")}
function add(i){if(needAcc())return;var p=G[cur].cats[tab][i],id=cur+"|"+tab+"|"+p[0];if(!p[3])return toast("Сервер недоступен, обнови страницу");C[id]=C[id]||{n:G[cur].n+" — "+p[0],p:p[2],pid:p[3],q:0};C[id].q++;sv();upd();toast("Добавлено в корзину")}
function chg(id,d){C[id].q=Math.min(10,C[id].q+d);if(C[id].q<1)delete C[id];sv();upd()}
var TOT=0,TXT="",PROMO=null;
function upd(){var ids=Object.keys(C),n=0;TOT=0;
 $("list").innerHTML=ids.length?ids.map(function(id){var o=C[id];n+=o.q;TOT+=o.q*o.p;return '<div class="row"><div><b>'+o.n+'</b><span>'+o.p+' ₽</span></div><div class="qty"><button onclick="chg(\''+id+'\',-1)">−</button><b>'+o.q+'</b><button onclick="chg(\''+id+'\',1)">+</button></div></div>'}).join(""):'<p class="empty">Пока пусто</p>';
 TXT=ids.map(function(id){return C[id].n+" x"+C[id].q}).join(", ");
 $("rc").innerHTML=ids.length?"🧾 "+ids.map(function(id){return "«"+C[id].n+"» — "+C[id].p+" ₽"+(C[id].q>1?" x"+C[id].q:"")}).join("<br>"):"";$("cnt").textContent=n;var DISC=0;if(PROMO&&TOT){DISC=TOT-(PROMO.type=="percent"?Math.round(TOT*(100-PROMO.value)/100):Math.max(TOT-PROMO.value,0))}$("sum").textContent=(TOT-DISC)+" ₽";$("pmsg").innerHTML=PROMO?("Промокод <b>"+PROMO.code+"</b>"+(DISC?": −"+DISC+" ₽":"")):"";$("buy").style.opacity=n?1:.45;$("buy").disabled=!n}
/* Оплата прямо на сайте: сервер бота создаёт платёж Platega (СБП), заказ привязан к Telegram-профилю */
var PAYTX="",PT=0;
try{PAYTX=localStorage.getItem("ptx")||""}catch(e){}
function authed(){return !!(INIT||SESS)}
function buy(){if(!TOT)return toast("Корзина пуста");
 if(needAcc())return;
 if(!authed()){panel("prof");toast("Сначала войди через Telegram");return}
 var m=document.querySelector("input[name=p]:checked"),btn=$("buy");btn.disabled=true;btn.style.opacity=.45;
 var items=Object.keys(C).map(function(k){return{id:C[k].pid,qty:C[k].q}});
 api("/api/pay",{items:items,method:m?m.value:2,tag:$("tag").value.trim(),promo:PROMO?PROMO.code:""}).then(function(r){
  btn.disabled=false;upd();
  if(!r.ok){if(r.need_register){REGD=false;needAcc();return}if(r.error==="auth"){INIT||(SESS="");toast("Войди через Telegram заново");panel("prof");return}if(/омокод/.test(r.error||"")){PROMO=null;upd()}return toast(r.error||"Не удалось создать платёж")}
  if(r.invoice){ /* оплата звёздами: счёт открывается прямо в Telegram */
   if(tg&&tg.openInvoice&&INIT){try{tg.openInvoice(r.invoice,function(st){if(st==="paid")paidOk({});else if(st==="failed")toast("Оплата не прошла, попробуй ещё раз");else toast("Оплата отменена")})}catch(e){window.open(r.invoice,"_blank")}}
   else{window.open(r.invoice,"_blank");toast("Оплати счёт в Telegram, детали заказа придут в бота",3500)}
   return}
  PAYTX=r.tx;try{localStorage.setItem("ptx",PAYTX)}catch(e){}
  $("payl").href=r.url;$("payl").style.display="";$("chk").style.display="";
  if(tg&&tg.openLink&&INIT){try{tg.openLink(r.url)}catch(e){window.open(r.url,"_blank")}}else{location.href=r.url}
  watchPay()}).catch(function(){btn.disabled=false;upd();toast("Сервер недоступен")})}
function paidOk(r){var _dr=r&&r.drops;PAYTX="";try{localStorage.removeItem("ptx")}catch(e){}clearInterval(PT);C={};PROMO=null;$("promo").value="";sv();upd();
 $("payl").style.display="none";$("chk").style.display="none";panel();toast(r.order_id?"Оплачено! Заказ №"+r.order_id+" — детали пришлём в боте":"Оплачено! Детали заказа пришлём в боте",3000);if(_dr&&_dr.length)csOpen(_dr);else if(!INIT&&BOT&&window.openBotPrompt)openBotPrompt(BOT)}
function checkPay(quiet){if(!PAYTX)return;
 api("/api/pay/"+encodeURIComponent(PAYTX)).then(function(r){if(!r.ok){if(r.error!=="auth")return;return}
  if(r.status==="paid")paidOk(r);
  else if(r.status==="canceled"){PAYTX="";try{localStorage.removeItem("ptx")}catch(e){}clearInterval(PT);$("payl").style.display="none";$("chk").style.display="none";toast("Платёж не прошёл или истёк")}
  else if(!quiet)toast("Оплата пока не поступила")}).catch(function(){})}
function watchPay(){clearInterval(PT);var n=0;PT=setInterval(function(){if(++n>180)return clearInterval(PT);checkPay(true)},4000)}
document.addEventListener("visibilitychange",function(){if(!document.hidden&&PAYTX)checkPay(true)});
if(PAYTX&&authed()){$("chk").style.display="";checkPay(true);watchPay()}
function applyPromo(){var c=$("promo").value.trim();if(!c){PROMO=null;upd();return}
 if(!authed()){panel("prof");toast("Сначала войди через Telegram");return}
 api("/api/promo?code="+encodeURIComponent(c)).then(function(r){if(!r.ok){PROMO=null;upd();return toast(r.error||"Промокод не найден")}PROMO={code:r.code,type:r.type,value:r.value};upd();toast("Промокод применён")})}
function panel(n){["cart","prof","adm"].forEach(function(i){$(i).classList.toggle("on",i==n)});$("shade").classList.toggle("on",!!n)}
document.addEventListener("keydown",function(e){if(e.key==="Escape")panel()});
function toast(m,ms){var t=$("toast");t.textContent=m;t.classList.add("on");clearTimeout(t._h);t._h=setTimeout(function(){t.classList.remove("on")},ms||1400)}
upd();loadShop();



/* ---- Регистрация: логин, почта, пароль, привязка к Telegram ---- */
var GM="reg",GCL=false,GBUSY=false;
function gShow(mode,closable){GCL=!!closable;$("gx").style.display=GCL?"":"none";
 $("seg").classList.toggle("hide",!!INIT); /* внутри Telegram вход по паролю не нужен: профиль уже известен */
 gMode(INIT?"reg":mode,true);$("gerr").textContent="";$("ghint").textContent="";var g=$("gate");g.classList.remove("out");g.classList.add("on");
 var c=$("gcard");c.style.animation="none";void c.offsetWidth;c.style.animation="";setTimeout(function(){try{$("g_login").focus({preventScroll:true})}catch(e){}},600)}
function gClose(){if(!GCL)return;var g=$("gate");g.classList.add("out");setTimeout(function(){g.classList.remove("on","out")},520)}
function gMode(m,quiet){GM=m;var reg=m=="reg";$("seg").classList.toggle("in",!reg);$("sg_reg").classList.toggle("on",reg);$("sg_in").classList.toggle("on",!reg);
 $("gf_mail").classList.toggle("hide",!reg);$("gh").textContent=reg?"Создать аккаунт":"С возвращением";
 $("gs").textContent=reg?"Придумай логин, почту и пароль. Это быстро.":"Войди по логину и паролю, который указал при регистрации.";
 $("gbt").textContent=reg?"Зарегистрироваться":"Войти";$("g_pw").autocomplete=reg?"new-password":"current-password";$("gerr").textContent="";
 if(!quiet){var i=$("segi");i.classList.remove("gel");void i.offsetWidth;i.classList.add("gel")}}
function gEye(){var p=$("g_pw"),h=p.type=="password";p.type=h?"text":"password";$("g_eye").textContent=h?"🙈":"👁"}
function gErr(m){$("gerr").textContent=m;var c=$("gcard");c.classList.remove("shake");void c.offsetWidth;c.classList.add("shake")}
function gRipple(e){var b=$("gbtn"),r=b.getBoundingClientRect(),d=document.createElement("span"),z=Math.max(r.width,r.height)/3;d.className="rp";
 d.style.cssText="width:"+z+"px;height:"+z+"px;left:"+((e&&e.clientX?e.clientX-r.left:r.width/2)-z/2)+"px;top:"+((e&&e.clientY?e.clientY-r.top:r.height/2)-z/2)+"px";b.appendChild(d);setTimeout(function(){d.remove()},650)}
function gSubmit(e){if(GBUSY)return;gRipple(e);
 var lg=$("g_login").value.trim(),em=$("g_mail").value.trim(),pw=$("g_pw").value,reg=GM=="reg";
 if(!/^[A-Za-z0-9_.-]{3,24}$/.test(lg))return gErr(reg?"Логин: 3-24 символа, латиница, цифры, . _ -":"Введи логин");
 if(reg&&!/^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$/.test(em))return gErr("Проверь почту, похоже на опечатку");
 if(reg&&pw.length<8)return gErr("Пароль не меньше 8 символов");
 if(!pw)return gErr("Введи пароль");
 if(reg&&!authed()){gErr("Сначала войди через Telegram, чтобы привязать аккаунт");login();return}
 GBUSY=true;$("gbtn").classList.add("load");$("gerr").textContent="";
 var done=function(){GBUSY=false;$("gbtn").classList.remove("load")};
 if(reg){api("/api/register",{login:lg,email:em,password:pw}).then(function(r){done();
   if(!r.ok){if(r.error==="auth"){INIT||(SESS="");return gErr("Сессия устарела, войди через Telegram заново")}return gErr(r.error||"Не получилось")}
   LOGIN=r.login;REGD=true;setUser(U);$("g_pw").value="";GCL=true;gClose();askWrite();toast("Аккаунт создан и привязан к Telegram",2600)}).catch(function(){done();gErr("Сервер недоступен")})}
 else{fetch(API+"/api/login/pw",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({login:lg,password:pw})}).then(function(x){return x.json()}).then(function(r){done();
   if(!r.ok)return gErr(r.error||"Не получилось");
   SESS=r.session;try{localStorage.setItem("ps",SESS)}catch(e){}$("g_pw").value="";REGD=true;LOGIN=lg;setUser(r.user);GCL=true;gClose();loadMe();toast("Ты вошёл как "+r.user.first_name,2200)}).catch(function(){done();gErr("Сервер недоступен")})}}
document.addEventListener("keydown",function(e){if(!$("gate").classList.contains("on"))return;if(e.key==="Enter")gSubmit();else if(e.key==="Escape")gClose()});
$("gcard").addEventListener("pointermove",function(e){var r=this.getBoundingClientRect();this.style.setProperty("--mx",(e.clientX-r.left)+"px");this.style.setProperty("--my",(e.clientY-r.top)+"px")});

/* ---- Админка (видна только админам; права проверяет сервер) ---- */
function esc(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function adm_(a,b){return api("/api/admin/"+a,b||{}).then(function(r){if(!r.ok){toast(r.error||"Ошибка",2800);throw r}return r})}
var AT="ov",AD={},AE=null;
var ATABS=[["ov","Обзор"],["pr","Товары"],["ct","Разделы"],["pm","Промо"],["or","Заказы"],["ch","Чаты"],["us","Люди"],["pay","Оплата"],["ad","Объявл."],["bc","Рассылка"]];
function openAdm(){if(!ISADM)return;panel("adm");admTab(AT)}
function admTab(t){AT=t;AE=null;$("atabs").innerHTML=ATABS.map(function(x){return '<button class="tab'+(x[0]==t?' on':'')+'" onclick="admTab(\''+x[0]+'\')">'+x[1]+'</button>'}).join("");
 $("abody").innerHTML='<p class="empty">Загрузка…</p>';({ov:aOv,pr:aPr,ct:aCt,pm:aPm,or:aOr,ch:aCh,us:aUs,pay:aPay,ad:aAd,bc:aBc})[t]()}
function aRefresh(){admTab(AT)}
function aOv(){adm_("overview").then(function(r){var u=r.users;$("abody").innerHTML='<div class="kpi">'+
 [[r.revenue+" ₽","Выручка (закрытые заказы)"],[r.orders,"Закрытых заказов"],[r.queue,"В очереди на выдачу"],[u.total,"Пользователей"],[u.new_24h,"Новых за 24 ч"],[u.active_24h,"Активны за 24 ч"]]
 .map(function(k){return '<div><b>'+esc(k[0])+'</b><span>'+k[1]+'</span></div>'}).join("")+'</div>'}).catch(function(){})}
/* товары */
function aPr(){adm_("catalog").then(function(r){AD=r;drawPr()}).catch(function(){})}
function stockTxt(s){return s<0?"безлимит":"остаток "+s}
function drawPr(){var h='<button class="sm pri" onclick="prForm(0)">+ Товар</button>';
 AD.cats.forEach(function(c){var ps=AD.prods.filter(function(p){return p.cat==c.key});
  h+='<div class="ac"><h5>'+esc(c.name)+' · '+esc((AD.games.filter(function(g){return g.id==c.game})[0]||{}).name||c.game)+(c.active?'':' · скрыт')+'</h5><div class="list">'+
  (ps.length?ps.map(function(p){return '<div class="arow'+(p.active?'':' off')+'"><div><b>'+esc(p.name)+'</b><span>'+p.price+' ₽ · '+stockTxt(p.stock)+'</span></div>'+
   '<button class="sm" onclick="prMove('+p.id+',\'up\')">↑</button><button class="sm" onclick="prMove('+p.id+',\'down\')">↓</button>'+
   '<button class="sm" onclick="prTog('+p.id+')">'+(p.active?'Скрыть':'Показать')+'</button><button class="sm pri" onclick="prForm('+p.id+')">Изм.</button></div>'}).join(""):'<span class="note">Пусто</span>')+'</div></div>'});
 $("abody").innerHTML=h}
function prMove(id,d){adm_("product_move",{id:id,dir:d}).then(aPr).catch(function(){})}
function prTog(id){adm_("product_toggle",{id:id}).then(aPr).catch(function(){})}
function prForm(id){var p=AD.prods.filter(function(x){return x.id==id})[0]||{name:"",desc:"",price:"",stock:-1,cat:AD.cats[0]&&AD.cats[0].key};
 $("abody").innerHTML='<div class="ac frm"><label>Название</label><input class="inp" id="f_n" maxlength="60" value="'+esc(p.name)+'">'+
 '<label>Описание</label><input class="inp" id="f_d" maxlength="200" value="'+esc(p.desc)+'">'+
 '<label>Цена, ₽</label><input class="inp" id="f_p" type="number" min="1" value="'+esc(p.price)+'">'+
 '<label>Остаток (-1 = безлимит)</label><input class="inp" id="f_s" type="number" min="-1" value="'+esc(p.stock)+'">'+
 '<label>Раздел</label><select class="inp" id="f_c">'+AD.cats.map(function(c){return '<option value="'+esc(c.key)+'"'+(c.key==p.cat?' selected':'')+'>'+esc(c.name)+' ('+esc(c.game)+')</option>'}).join("")+'</select>'+
 '<div style="display:flex;gap:8px"><button class="btn main" style="margin:0;flex:1" onclick="prSave('+(id||0)+')">Сохранить</button><button class="btn gl" style="margin:0" onclick="drawPr()">Отмена</button></div></div>'}
function prSave(id){adm_("product_save",{id:id||undefined,name:$("f_n").value,desc:$("f_d").value,price:$("f_p").value,stock:$("f_s").value,cat:$("f_c").value})
 .then(function(){toast("Сохранено");aPr()}).catch(function(){})}
/* разделы */
function aCt(){adm_("catalog").then(function(r){AD=r;drawCt()}).catch(function(){})}
function drawCt(){var h='<button class="sm pri" onclick="ctForm()">+ Раздел</button><div class="list">'+AD.cats.map(function(c){
 return '<div class="arow'+(c.active?'':' off')+'"><div><b>'+esc(c.name)+'</b><span>'+esc((AD.games.filter(function(g){return g.id==c.game})[0]||{}).name||c.game)+'</span></div>'+
 '<button class="sm" onclick="ctMove(\''+c.key+'\',\'up\')">↑</button><button class="sm" onclick="ctMove(\''+c.key+'\',\'down\')">↓</button>'+
 '<button class="sm" onclick="ctTog(\''+c.key+'\')">'+(c.active?'Скрыть':'Показать')+'</button><button class="sm pri" onclick="ctForm(\''+c.key+'\')">Имя</button>'+
 (c.base?'':'<button class="sm dng" onclick="ctDel(\''+c.key+'\')">✕</button>')+'</div>'}).join("")+'</div>';$("abody").innerHTML=h}
function ctMove(k,d){adm_("category_move",{key:k,dir:d}).then(aCt).catch(function(){})}
function ctTog(k){adm_("category_toggle",{key:k}).then(aCt).catch(function(){})}
function ctDel(k){if(!confirm("Удалить раздел? Товары из него останутся без раздела."))return;adm_("category_delete",{key:k}).then(aCt).catch(function(){})}
function ctForm(k){var c=k&&AD.cats.filter(function(x){return x.key==k})[0];
 $("abody").innerHTML='<div class="ac frm"><label>Название раздела</label><input class="inp" id="g_n" maxlength="40" value="'+esc(c?c.name:"")+'">'+
 (c?'':'<label>Игра</label><select class="inp" id="g_g">'+AD.games.map(function(g){return '<option value="'+g.id+'">'+esc(g.name)+'</option>'}).join("")+'</select>')+
 '<div style="display:flex;gap:8px"><button class="btn main" style="margin:0;flex:1" onclick="ctSave(\''+(k||"")+'\')">Сохранить</button><button class="btn gl" style="margin:0" onclick="drawCt()">Отмена</button></div></div>'}
function ctSave(k){adm_("category_save",{key:k||undefined,name:$("g_n").value,game:k?undefined:$("g_g").value}).then(function(){toast("Сохранено");aCt()}).catch(function(){})}
/* промокоды */
function aPm(){adm_("promo_list").then(function(r){AD.pm=r.promos;drawPm()}).catch(function(){})}
function drawPm(){$("abody").innerHTML='<div class="ac frm"><label>Новый промокод</label><input class="inp" id="m_c" maxlength="20" placeholder="CODE" autocapitalize="characters">'+
 '<div style="display:flex;gap:8px"><select class="inp" id="m_t"><option value="percent">Процент, %</option><option value="amount">Сумма, ₽</option></select><input class="inp" id="m_v" type="number" min="1" placeholder="Размер"></div>'+
 '<button class="btn main" style="margin:0" onclick="pmSave()">Добавить</button></div><div class="list">'+
 (AD.pm.length?AD.pm.map(function(p){return '<div class="arow'+(p.active?'':' off')+'"><div><b>'+esc(p.code)+'</b><span>−'+p.value+(p.type=="percent"?"%":" ₽")+'</span></div>'+
  '<button class="sm" onclick="pmTog(\''+p.code+'\')">'+(p.active?'Выкл':'Вкл')+'</button><button class="sm dng" onclick="pmDel(\''+p.code+'\')">✕</button></div>'}).join(""):'<p class="empty">Промокодов нет</p>')+'</div>'}
function pmSave(){adm_("promo_save",{code:$("m_c").value,type:$("m_t").value,value:$("m_v").value}).then(function(){toast("Добавлено");aPm()}).catch(function(){})}
function pmTog(c){adm_("promo_toggle",{code:c}).then(aPm).catch(function(){})}
function pmDel(c){if(!confirm("Удалить промокод "+c+"?"))return;adm_("promo_delete",{code:c}).then(aPm).catch(function(){})}
/* объявление после оплаты */
function aAd(){adm_("notice_get").then(function(r){AD.nt=r;
 $("abody").innerHTML='<div class="ac frm"><label>Объявление приходит покупателю в бот сразу после оплаты</label>'+
 '<select class="inp" id="n_on"><option value="1"'+(r.on?' selected':'')+'>Включено</option><option value="0"'+(r.on?'':' selected')+'>Выключено</option></select>'+
 '<label>Текст</label><textarea class="inp" id="n_t" rows="4" maxlength="500" placeholder="'+esc(r.default_text)+'">'+esc(r.text)+'</textarea>'+
 '<label>Ссылка на канал (https://t.me/...)</label><input class="inp" id="n_u" maxlength="200" placeholder="'+esc(r.default_url||"https://t.me/...")+'" value="'+esc(r.url)+'">'+
 '<span class="note">Пустые поля = текст и ссылка по умолчанию.</span>'+
 '<div style="display:flex;gap:8px"><button class="btn main" style="margin:0;flex:1" onclick="ntSave()">Сохранить</button><button class="btn gl" style="margin:0" onclick="ntTest()">Тест мне в бот</button></div></div>'}).catch(function(){})}
function ntSave(cb){adm_("notice_save",{on:$("n_on").value=="1",text:$("n_t").value,url:$("n_u").value.trim()}).then(function(){toast("Сохранено");if(cb)cb()}).catch(function(){})}
function ntTest(){ntSave(function(){adm_("notice_test").then(function(r){toast(r.msg,2500)}).catch(function(){})})}
/* рассылка */
var BT=null;
function aBc(){adm_("bcast_info").then(function(r){AD.bc=r;
 $("abody").innerHTML='<div class="ac frm"><label>Сообщение уйдёт в Telegram от бота. Получателей: '+r.users+' (с аккаунтом: '+r.accounts+')</label>'+
 '<textarea class="inp" id="b_t" rows="5" maxlength="3500" placeholder="Текст рассылки"></textarea>'+
 '<label>Кнопка-ссылка (необязательно)</label><input class="inp" id="b_bt" maxlength="40" placeholder="Текст кнопки, например: Открыть магазин">'+
 '<input class="inp" id="b_bu" maxlength="300" placeholder="https://...">'+
 '<label>Кому</label><select class="inp" id="b_a"><option value="all">Всем пользователям бота</option><option value="reg">Только с аккаунтом</option></select>'+
 '<div id="b_st" class="note"></div>'+
 '<div style="display:flex;gap:8px"><button class="btn gl" style="margin:0" onclick="bcSend(\'me\')">Тест мне</button><button class="btn main" style="margin:0;flex:1" onclick="bcSend()">Отправить</button></div></div>';
 bcPoll(r.status)}).catch(function(){})}
function bcSend(me){var a=me?"me":$("b_a").value,n=AD.bc?(a=="reg"?AD.bc.accounts:AD.bc.users):0;
 if(!me&&!confirm("Отправить рассылку: "+n+" получателям? Отменить будет нельзя."))return;
 adm_("bcast_send",{text:$("b_t").value,btn_text:$("b_bt").value,btn_url:$("b_bu").value.trim(),audience:a}).then(function(){toast(me?"Тест отправлен":"Рассылка пошла");bcPoll()}).catch(function(){})}
function bcPoll(st){clearTimeout(BT);var show=function(s){var el=$("b_st");if(!el||AT!="bc")return false;
  el.textContent=s.running?"Идёт рассылка: "+s.sent+" из "+s.total+(s.failed?" (не доставлено: "+s.failed+")":""):(s.total?"Готово: доставлено "+s.sent+" из "+s.total+(s.failed?", не доставлено: "+s.failed:""):"");return s.running};
 if(st&&!show(st))return;
 BT=setTimeout(function(){if(AT!="bc")return;adm_("bcast_status").then(function(r){if(show(r.status))bcPoll()}).catch(function(){})},1200)}
/* заказы */
var OTODO=true;
function aOr(){adm_("orders",{todo:OTODO}).then(function(r){var ST={pending:"ждёт проверки",confirmed:"оплачен",completed:"закрыт",rejected:"отклонён",cancelled:"отменён"};
 $("abody").innerHTML='<div class="tabs" style="margin:0"><button class="tab'+(OTODO?' on':'')+'" onclick="OTODO=true;aOr()">К выдаче</button><button class="tab'+(OTODO?'':' on')+'" onclick="OTODO=false;aOr()">Все</button></div>'+
 (r.orders.length?r.orders.map(function(o){var can=o.status=="confirmed"&&!o.delivered;
  return '<div class="arow"><div><b>№'+o.id+' · '+esc(o.name)+'</b><span>'+o.price+' ₽ · '+esc(ST[o.status]||o.status)+(o.delivered&&o.status=="confirmed"?' · выдан':'')+' · '+(o.username?'@'+esc(o.username):'id '+o.user)+'</span></div>'+
  '<button class="sm" onclick="openOrderChat('+o.id+')">Чат</button>'+(can?'<button class="sm pri" onclick="ordDeliver('+o.id+')">Выдано</button>':'')+'</div>'}).join(""):'<p class="empty">Заказов нет</p>')}).catch(function(){})}
function ordDeliver(id){if(!confirm("Отметить заказ №"+id+" выданным? Покупателю уйдёт кнопка подтверждения."))return;adm_("deliver",{id:id}).then(function(r){toast(r.msg,2500);aOr()}).catch(function(){})}

/* ---- FAQ ---- */
var FQ=[["Какие гарантии я получаю?","Заказ выполняется вручную, по каждому есть поддержка. Если что-то пошло не так, пиши в поддержку, разберёмся. Подробности в пользовательском соглашении."],["Как быстро придёт товар?","Обычно в течение нескольких минут после оплаты. В часы высокой нагрузки может занять чуть больше."],["Нужен ли пароль от аккаунта?","Пароль от аккаунта не нужен и мы его не запрашиваем. Перед покупкой прочитай страницу «Проверка аккаунта»."],["Может ли зачисление быть отменено позже?","Шанс отката доната составляет 15%. Если зачисление пропало, сразу пиши в поддержку, разберёмся."],["Как я узнаю статус заказа?","Статус и очередь видны в боте, там же придёт уведомление о выдаче."],["Можно ли вернуть уже выданный товар?","После выдачи цифровой товар возврату не подлежит. Если выдача не произошла по нашей вине, мы вернём оплату."],["Как оплатить через СБП?","В корзине выбери СБП, нажми «Оплатить» и подтверди платёж в приложении своего банка. Заказ сам привяжется к твоему профилю Telegram."]];
$("faqBox").innerHTML=FQ.map(function(q){return '<div class="q glass"><button onclick="this.parentNode.classList.toggle(\'on\')">'+q[0]+'</button><div>'+q[1]+'</div></div>'}).join("");

/* ---- Подсветка меню ---- */
var secs=["top","games","faq","help"],nav=document.querySelectorAll("#tabbar a,#links a");
new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)nav.forEach(function(a){a.classList.toggle("on",a.getAttribute("href")=="#"+e.target.id)})})},{rootMargin:"-40% 0px -55% 0px"}).observe&&secs.forEach(function(){});
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)nav.forEach(function(a){a.classList.toggle("on",a.getAttribute("href")=="#"+e.target.id)})})},{rootMargin:"-40% 0px -55% 0px"});
secs.forEach(function(s){io.observe($(s))});

/* картинки баннеров: если файл data-img лежит в папке site, ставим его фоном, иначе остаётся градиент */
document.querySelectorAll(".bn[data-img]").forEach(function(b){var u=b.dataset.img,im=new Image();im.onload=function(){b.style.backgroundImage="linear-gradient(0deg,rgba(2,11,7,.75),rgba(2,11,7,.1)),url("+u+")"};im.src=u});

/* ---- Pass Case: анимация открытия (результат приходит с сервера, анимация только показывает его) ---- */
var CSN=["Brawl Pass","Brawl Pass Plus","Pro Pass"],CSQ=[],CSBUSY=false;
function csItem(i){return '<div class="cs-it p'+i+'">'+CSN[i]+'<small>33,3%</small></div>'}
function csOpen(drops){
 if(!drops||!drops.length)return false;
 CSQ=drops.slice();csNext();return true}
function csNext(){
 var d=CSQ.shift();if(!d){csClose();return}
 var win=CSN.indexOf(d);if(win<0)win=0;
 var tr=$("cstr"),n=48,pos=40,html="";
 for(var i=0;i<n;i++){html+=csItem(i===pos?win:Math.floor(Math.random()*3))}
 tr.style.transition="none";tr.style.transform="translateX(0)";tr.innerHTML=html;
 $("csres").classList.remove("on");$("csok").classList.remove("on");$("cs").classList.add("on");CSBUSY=true;
 var w=tr.parentNode.clientWidth,itw=128;
 var target=pos*itw+itw/2-w/2+(Math.random()*60-30);
 void tr.offsetWidth;
 setTimeout(function(){tr.style.transition="transform 5.2s cubic-bezier(.08,.6,.12,1)";tr.style.transform="translateX("+(-target)+"px)"},60);
 setTimeout(function(){CSBUSY=false;var r=$("csres");r.textContent="Тебе выпал: "+CSN[win]+(CSQ.length?" (ещё кейсов: "+CSQ.length+")":"");r.classList.add("on");$("csok").textContent=CSQ.length?"Открыть следующий":"Забрать";$("csok").classList.add("on")},5500)}
function csClose(){if(CSBUSY)return;if(CSQ.length){csNext();return}$("cs").classList.remove("on")}
