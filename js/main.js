// ===== Portfolio — main.js =====
(function () {
  'use strict';

  var isArabic = document.documentElement.dir === 'rtl' || document.documentElement.lang === 'ar';

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

  // Contact form -> mailto: (client-side, no backend/domain verification needed)
  var form = document.querySelector('#contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      var status = form.querySelector('.form-status');
      var name = form.querySelector('[name="name"]').value.trim();
      var email = form.querySelector('[name="email"]').value.trim();
      var message = form.querySelector('[name="message"]').value.trim();
      var subject = '[Portfolio] New inquiry from ' + (name || 'Visitor');
      var body = 'Name: ' + name + '%0A'
               + 'Email: ' + email + '%0A'
               + 'Message:%0A' + message;
      var mailtoUrl = 'mailto:cd3alaa@yahoo.com?subject='
                    + encodeURIComponent(subject)
                    + '&body=' + encodeURIComponent(body);
      btn.disabled = true;
      btn.textContent = isArabic ? 'جاري...' : 'Opening mail…';
      status.className = 'form-status sending';
      status.textContent = isArabic ? 'جارٍ فتح عميل البريد…' : 'Opening your email client…';
      window.location.href = mailtoUrl;
      form.reset();
      status.className = 'form-status ok';
      status.textContent = isArabic ? 'شكراً! تم فتح بريدك — سيرسل رسالتك. سأرد عليك قريباً.' : 'Thank you! Your email client opened — send the message and I will reply soon.';
      btn.disabled = false;
      btn.textContent = isArabic ? 'إرسال الاستفسار ←' : 'Send inquiry →';
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
