/* Portfolio Chat widget — vanilla JS, no dependencies, site-convention safe. */
(function () {
  'use strict';

  var DEFAULTS = { apiUrl: '', whatsapp: '201553851517', lang: 'ar' };
  var config = {};
  var sessionId = null;
  var els = {};
  var unread = 0;
  var panelOpen = false;
  var busy = false; // a request is in flight

  var ICON_CHAT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>';
  var ICON_WA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.5 14.4c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48-.89-.79-1.49-1.77-1.66-2.07-.17-.3-.02-.46.13-.61.14-.13.3-.35.45-.52.15-.18.2-.3.3-.5.1-.2.05-.38-.02-.53-.08-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.49 0 1.47 1.07 2.89 1.22 3.09.15.2 2.11 3.22 5.1 4.51.71.31 1.27.49 1.7.63.72.23 1.37.2 1.88.12.58-.09 1.76-.72 2.01-1.42.25-.7.25-1.29.17-1.42-.07-.13-.27-.2-.57-.35zM12 2a10 10 0 0 0-8.66 15L2 22l5.13-1.34A10 10 0 1 0 12 2z"/></svg>';

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text; // XSS-safe
    return node;
  }

  function isArabic(text) {
    return /[\u0600-\u06FF]/.test(text);
  }

  function localize(ar, en) {
    var pageRtl = document.documentElement.getAttribute('dir') === 'rtl';
    var pageAr = pageRtl || (config.lang === 'ar') || isArabic(document.title);
    return pageAr ? ar : en;
  }

  function api(sessionMsg, cb) {
    if (!config.apiUrl) {
      if (cb) cb({ messages: [localize('عذراً، البوت غير متصل الآن.', 'Sorry, the assistant is offline right now.')], quick_replies: [], whatsapp: null, state: '' });
      return;
    }
    var url = config.apiUrl + (config.apiUrl.slice(-5) === '/chat' ? '' : '/chat');
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: sessionMsg, page_lang: config.lang })
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(cb)
      .catch(function () {
        if (cb) cb({ messages: [localize('حدث خطأ — جرّب مرة أخرى أو تواصل واتساب.', 'Something went wrong — try again or reach me on WhatsApp.')], quick_replies: [], whatsapp: null, state: '' });
      });
  }

  function build() {
    var fab = el('button', 'pf-chat-fab');
    fab.setAttribute('aria-label', localize('فتح المحادثة', 'Open chat'));
    fab.innerHTML = ICON_CHAT;
    var unreadNode = el('span', 'pf-chat-unread', '1');
    unreadNode.style.display = 'none';
    fab.appendChild(unreadNode);

    els.wrapper = el('div', 'pf-chat-panel');
    els.wrapper.style.display = 'none';

    var header = el('div', 'pf-chat-header');
    var avatar = el('div', 'pf-chat-avatar', 'أ');
    avatar.textContent = localize('أ', 'A');
    var titleWrap = el('div');
    titleWrap.appendChild(el('div', 'pf-chat-title', localize('مساعد أحمد', 'Ahmed Assistant')));
    titleWrap.appendChild(el('div', 'pf-chat-sub', localize('خدمات · مشاريع · استشارة', 'Services · Projects · Advice')));
    var close = el('button', 'pf-chat-close', localize('✕', '✕'));
    close.setAttribute('aria-label', localize('إغلاق', 'Close'));
    header.appendChild(avatar);
    header.appendChild(titleWrap);
    header.appendChild(close);

    els.body = el('div', 'pf-chat-body');

    var inputBar = el('div', 'pf-chat-input');
    els.input = el('input');
    els.input.setAttribute('type', 'text');
    els.input.setAttribute('placeholder', localize('اكتب رسالتك…', 'Type your message…'));
    els.input.setAttribute('autocomplete', 'off');
    els.input.setAttribute('aria-label', localize('رسالتك', 'Your message'));
    var send = el('button', '');
    send.setAttribute('aria-label', localize('إرسال', 'Send'));
    send.innerHTML = ICON_SEND;
    inputBar.appendChild(els.input);
    inputBar.appendChild(send);

    els.wrapper.appendChild(header);
    els.wrapper.appendChild(els.body);
    els.wrapper.appendChild(inputBar);

    els.fab = fab;

    document.body.appendChild(fab);
    document.body.appendChild(els.wrapper);

    fab.addEventListener('click', function () { toggle(true); });
    close.addEventListener('click', function () { toggle(false); });
    send.addEventListener('click', function () { submit(); });
    els.input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
  }

  function toggle(open) {
    panelOpen = open;
    els.wrapper.style.display = open ? 'flex' : 'none';
    els.wrapper.style.visibility = open ? 'visible' : 'hidden';
    els.fab.querySelector('.pf-chat-unread').style.display = 'none';
    unread = 0;
    if (open && els.body.children.length === 0) {
      addTyping();
      api('start', function (reply) {
        removeTyping();
        render(reply);
      });
    }
    if (open) els.input.focus();
  }

  function addTyping() {
    var t = el('div', 'pf-msg pf-typing');
    t.innerHTML = '<i></i><i></i><i></i>';
    els.body.appendChild(t);
    els.body.scrollTop = els.body.scrollHeight;
  }
  function removeTyping() {
    var t = els.body.querySelector('.pf-typing');
    if (t) t.remove();
  }

  function render(reply) {
    (reply.messages || []).forEach(function (m) {
      els.body.appendChild(el('div', 'pf-msg bot', m));
    });
    if (reply.quick_replies && reply.quick_replies.length) {
      var box = el('div', 'pf-quick');
      reply.quick_replies.forEach(function (label) {
        var b = el('button', '', label);
        b.addEventListener('click', function () { submit(label); });
        box.appendChild(b);
      });
      els.body.appendChild(box);
    }
    if (reply.state === 'offer_whatsapp') {
      var hint = el('div', 'pf-msg bot pf-lead-hint', localize('اقتراح: لو تفضل أرجّع لك أنا، اترك رقمك أو إيميلك في محادثتك.', 'Tip: if you prefer I contact you, leave your phone or email here.'));
      els.body.appendChild(hint);
    }
    if (reply.whatsapp && reply.whatsapp.link) {
      var a = document.createElement('a');
      a.className = 'pf-wa';
      a.href = reply.whatsapp.link;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML = ICON_WA;
      a.appendChild(el('span', '', localize('متابعة على واتساب', 'Continue on WhatsApp')));
      els.body.appendChild(a);
    }
    // generic WhatsApp fallback link in footer of conversation
    if (!els.hasWaLinks) {
      var link = document.createElement('a');
      link.className = 'pf-wa';
      link.href = 'https://wa.me/' + config.whatsapp + '?text=' + encodeURIComponent(localize('مرحباً، وجدت بورتفوليو أحمد وأود الاستفسار.', "Hi, I found Ahmed's portfolio and I'd like to ask."));
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.innerHTML = ICON_WA;
      link.appendChild(el('span', '', localize('تواصل مباشرة واتساب', 'Chat on WhatsApp')));
      els.body.appendChild(link);
      els.hasWaLinks = true;
    }
    els.body.scrollTop = els.body.scrollHeight;
    if (!panelOpen) {
      unread += 1;
      var n = els.fab.querySelector('.pf-chat-unread');
      n.textContent = String(unread);
      n.style.display = 'grid';
    }
  }

  function submit(text) {
    var msg = (text !== undefined) ? text : els.input.value.trim();
    if (!msg || busy) return;
    busy = true;
    els.input.value = '';
    els.body.appendChild(el('div', 'pf-msg user', msg));
    addTyping();
    api(msg, function (reply) {
      busy = false;
      removeTyping();
      render(reply);
    });
  }

  function persistSession() {
    try {
      if (!sessionId) {
        sessionId = localStorage.getItem('pf_chat_sid');
        if (!sessionId) {
          sessionId = 'w' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
          localStorage.setItem('pf_chat_sid', sessionId);
        }
      }
    } catch (e) { sessionId = 'w' + Date.now().toString(36); }
  }

  window.PortfolioChat = {
    init: function (opts) {
      config = {};
      var k;
      for (k in DEFAULTS) { config[k] = opts && opts[k] !== undefined ? opts[k] : DEFAULTS[k]; }
      persistSession();
      build();
    }
  };
})();