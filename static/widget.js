(function () {
  var script = document.currentScript;
  if (!script) return;
  var tenant = script.getAttribute("data-tenant");
  if (!tenant) { console.error("Sanvad: data-tenant attribute is required"); return; }

  var api = script.getAttribute("data-api") || new URL(script.src).origin;
  var title = script.getAttribute("data-title") || "Chat with us";
  var greeting = script.getAttribute("data-greeting") || "Hi! How can I help you today?";
  var color = script.getAttribute("data-color") || "#2563eb";
  if (!/^#[0-9a-fA-F]{3,8}$/.test(color)) color = "#2563eb";

  var host = document.createElement("div");
  host.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:2147483647;";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  root.innerHTML =
    '<style>' +
    ':host{all:initial}' +
    '*{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans Devanagari",sans-serif}' +
    '.fab{width:56px;height:56px;border-radius:50%;border:0;background:' + color + ';color:#fff;font-size:26px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)}' +
    '.panel{display:none;flex-direction:column;width:360px;max-width:calc(100vw - 24px);height:500px;max-height:calc(100vh - 100px);background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.28);overflow:hidden;margin-bottom:12px}' +
    '.panel.open{display:flex}' +
    '.head{background:' + color + ';color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}' +
    '.close{background:none;border:0;color:#fff;font-size:20px;cursor:pointer}' +
    '.msgs{flex:1;overflow-y:auto;padding:12px;background:#f5f6f8;display:flex;flex-direction:column;gap:8px}' +
    '.m{max-width:82%;padding:9px 12px;border-radius:12px;font-size:14px;line-height:1.4;white-space:normal;word-wrap:break-word}' +
    '.m.bot{background:#fff;color:#1f2937;align-self:flex-start;border:1px solid #e5e7eb}' +
    '.m.user{background:' + color + ';color:#fff;align-self:flex-end;white-space:pre-wrap}' +
    '.m.note{background:transparent;border:0;color:#6b7280;font-style:italic}' +
    '.m ul{margin:4px 0;padding-left:18px}' +
    '.row{display:flex;gap:8px;padding:10px;border-top:1px solid #e5e7eb;background:#fff}' +
    'input{flex:1;border:1px solid #d1d5db;border-radius:8px;padding:9px 10px;font-size:14px;outline:none}' +
    'input:focus{border-color:' + color + '}' +
    '.send{background:' + color + ';color:#fff;border:0;border-radius:8px;padding:0 14px;cursor:pointer;font-size:14px}' +
    '.send:disabled{opacity:.5;cursor:default}' +
    '</style>' +
    '<div class="panel" id="panel">' +
    '<div class="head"><span id="title"></span><button class="close" id="close" aria-label="Close">&times;</button></div>' +
    '<div class="msgs" id="msgs"></div>' +
    '<div class="row"><input id="inp" maxlength="1000" placeholder="Type your question..." autocomplete="off">' +
    '<button class="send" id="send">Send</button></div></div>' +
    '<button class="fab" id="fab" aria-label="Open chat">&#128172;</button>';

  var $ = function (id) { return root.getElementById(id); };
  var panel = $("panel"), msgs = $("msgs"), inp = $("inp"), send = $("send");
  $("title").textContent = title;

  var history = [];
  var busy = false;

  function inline(parent, text) {
    text.split(/(\*\*[^*]+\*\*)/).forEach(function (part) {
      if (/^\*\*[^*]+\*\*$/.test(part)) {
        var s = document.createElement("strong");
        s.textContent = part.slice(2, -2);
        parent.appendChild(s);
      } else if (part) {
        parent.appendChild(document.createTextNode(part));
      }
    });
  }

  function fmt(el, text) {
    var list = null;
    text.split("\n").forEach(function (line) {
      var m = line.match(/^\s*[-*\u2022]\s+(.*)$/);
      if (m) {
        if (!list) { list = document.createElement("ul"); el.appendChild(list); }
        var li = document.createElement("li");
        inline(li, m[1]);
        list.appendChild(li);
      } else {
        list = null;
        var d = document.createElement("div");
        if (line.trim()) inline(d, line); else d.style.height = "6px";
        el.appendChild(d);
      }
    });
  }

  function add(text, cls) {
    var d = document.createElement("div");
    d.className = "m " + cls;
    if (cls === "bot") fmt(d, text); else d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  function addLink(url) {
    if (!/^https:\/\/wa\.me\//.test(url)) return;
    var d = document.createElement("div");
    d.className = "m note";
    var a = document.createElement("a");
    a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer";
    a.style.color = color;
    a.textContent = "Talk to our team on WhatsApp";
    d.appendChild(a);
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  }

  add(greeting, "bot");

  $("fab").onclick = function () {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) inp.focus();
  };
  $("close").onclick = function () { panel.classList.remove("open"); };

  async function submit() {
    var text = inp.value.trim();
    if (!text || busy) return;
    busy = true; send.disabled = true; inp.value = "";
    add(text, "user");
    var typing = add("Typing...", "note");
    var timer = null;
    try {
      var res = await fetch(api + "/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenant, message: text, history: history.slice(-6) })
      });
      if (!res.ok) {
        typing.remove(); typing = null;
        if (res.status === 404) add("This chat is not available right now.", "note");
        else if (res.status === 403) add("This website is not allowed to use this chat.", "note");
        else if (res.status === 429) add("Too many messages. Please wait a moment.", "note");
        else if (res.status === 503) add("The assistant is busy right now. Please try again in a moment.", "note");
        else add("Something went wrong. Please try again.", "note");
      } else {
        var bot = null, full = "", shown = 0, escalation = null, failed = false;

        timer = setInterval(function () {
          if (!bot || shown >= full.length) return;
          shown += Math.max(2, Math.ceil((full.length - shown) / 40));
          bot.textContent = "";
          fmt(bot, full.slice(0, shown));
          msgs.scrollTop = msgs.scrollHeight;
        }, 20);

        var handle = function (line) {
          if (!line.trim()) return;
          var ev = JSON.parse(line);
          if (ev.t === "delta") {
            if (typing) { typing.remove(); typing = null; }
            if (!bot) bot = add("", "bot");
            full += ev.text;
          } else if (ev.t === "done") {
            escalation = ev.escalation_url;
          } else if (ev.t === "error") {
            failed = true;
          }
        };

        var reader = res.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        while (true) {
          var r = await reader.read();
          if (r.done) break;
          buf += dec.decode(r.value, { stream: true });
          var lines = buf.split("\n");
          buf = lines.pop();
          lines.forEach(handle);
        }
        if (buf.trim()) handle(buf);

        while (shown < full.length) {
          await new Promise(function (ok) { setTimeout(ok, 20); });
        }
        clearInterval(timer); timer = null;

        if (typing) { typing.remove(); typing = null; }
        if (failed && !full) add("Something went wrong. Please try again.", "note");
        if (full) {
          history.push({ role: "user", content: text });
          history.push({ role: "assistant", content: full.slice(0, 2000) });
        }
        if (escalation) addLink(escalation);
      }
    } catch (e) {
      if (timer) clearInterval(timer);
      if (typing) typing.remove();
      add("Could not reach the server. Please try again.", "note");
    }
    busy = false; send.disabled = false; inp.focus();
  }

  send.onclick = submit;
  inp.addEventListener("keydown", function (e) { if (e.key === "Enter") submit(); });
})();