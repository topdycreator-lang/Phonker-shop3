/* Подсказка "Добавить на главный экран". Показывается один раз, не в Telegram и не в установленном приложении. */
(function(){
var KEY="a2hs_seen",dp=null;
function seen(){try{return localStorage.getItem(KEY)}catch(e){return null}}
function mark(){try{localStorage.setItem(KEY,"1")}catch(e){}}
var tg=window.Telegram&&Telegram.WebApp&&Telegram.WebApp.initData;
var standalone=window.matchMedia&&matchMedia("(display-mode: standalone)").matches||navigator.standalone;
if(tg||standalone)return;
window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();dp=e});
var ios=/iphone|ipad|ipod/i.test(navigator.userAgent);
function close(){var n=document.getElementById("a2");if(n)n.remove();mark()}
function show(){
 if(document.getElementById("a2"))return;
 var s=ios?["Открой меню браузера и нажми «Поделиться»","Выбери «На экран Домой»","Нажми «Добавить»"]:["Открой меню браузера (три точки)","Выбери «Добавить на главный экран» или «Установить»","Подтверди"];
 var d=document.createElement("div");d.id="a2";d.className="on";
 d.innerHTML='<div class="bx"><button class="x" aria-label="Закрыть">✕</button><h3>Сохрани Phonker Shop на экране «Домой»</h3><p>Магазин всегда под рукой.</p>'+s.map(function(t,i){return '<div class="st"><i>'+(i+1)+'</i><span>'+t+'</span></div>'}).join("")+'<button class="go">'+(dp?"Установить":"Понятно")+'</button></div>';
 document.body.appendChild(d);
 d.querySelector(".x").onclick=close;
 d.querySelector(".go").onclick=function(){if(dp){dp.prompt();}close()};
}
window.showA2HS=show;
window.addEventListener("load",function(){if(!seen())setTimeout(show,4000)});
})();
