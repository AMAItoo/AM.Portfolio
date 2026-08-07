// ===== Portfolio — main.js =====
(function () {
  'use strict';

  // Mobile nav toggle
  var toggle = document.querySelector('.nav-toggle');
  var links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      links.classList.toggle('open');
      toggle.classList.toggle('active');
    });
    links.addEventListener('click', function (e) {
      if (e.target.closest('a')) links.classList.remove('open');
    });
  }

  // Reveal on scroll
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('visible');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('visible'); });
  }

  // Protect previews: no right-click, no drag on protected elements
  document.addEventListener('contextmenu', function (e) {
    if (e.target.closest('.protect')) e.preventDefault();
  });
  document.addEventListener('dragstart', function (e) {
    if (e.target.closest('.protect')) e.preventDefault();
  });
  document.addEventListener('selectstart', function (e) {
    if (e.target.closest('.protect')) e.preventDefault();
  });

  // Contact form -> FormSubmit (AJAX, no backend needed)
  var form = document.querySelector('#contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      var status = form.querySelector('.form-status');
      var data = new FormData(form);
      data.set('_subject', '[Portfolio] New inquiry');
      data.set('_captcha', 'false');
      data.set('_template', 'table');
      btn.disabled = true;
      btn.textContent = 'Sending…';
      status.className = 'form-status sending';
      status.textContent = 'Sending your message…';
      fetch(form.action, { method: 'POST', body: data, headers: { 'Accept': 'application/json' } })
        .then(function (res) { return res.json(); })
        .then(function (json) {
          if (json.success === 'true' || json.success === true) {
            status.className = 'form-status ok';
            status.textContent = 'Thank you! Your message was sent — I will reply soon.';
            form.reset();
          } else if (json.success === 'false') {
            status.className = 'form-status err';
            status.textContent = 'Email activation needed first — check your inbox for the confirmation link.';
          } else {
            status.className = 'form-status err';
            status.textContent = 'Could not send. Please try again or message me on WhatsApp.';
          }
        })
        .catch(function () {
          status.className = 'form-status err';
          status.textContent = 'Could not send. Please try again or message me on WhatsApp.';
        })
        .finally(function () {
          btn.disabled = false;
          btn.textContent = 'Send inquiry →';
        });
    });
  }

  // Copy email to clipboard
  var copyBtn = document.querySelector('[data-copy]');
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      var t = copyBtn.getAttribute('data-copy');
      var done = copyBtn.querySelector('.done');
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(function () { flash(done); });
      } else {
        var ta = document.createElement('textarea');
        ta.value = t; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); flash(done); } catch (err) {}
        document.body.removeChild(ta);
      }
      function flash(el) { if (el) { el.style.opacity = '1'; setTimeout(function () { el.style.opacity = '0'; }, 1600); } }
    });
  }
})();
