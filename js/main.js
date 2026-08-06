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

  // Contact form -> mailto (no backend needed; replace address when ready)
  var form = document.querySelector('#contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var name = form.querySelector('[name="name"]').value.trim();
      var msg = form.querySelector('[name="message"]').value.trim();
      var subject = 'Portfolio inquiry' + (name ? ' from ' + name : '');
      var body = encodeURIComponent(msg + '\n\n— ' + name);
      window.location.href = 'mailto:hello@youremail.com?subject=' + encodeURIComponent(subject) + '&body=' + body;
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
