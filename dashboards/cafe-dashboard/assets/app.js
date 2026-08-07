(function () {
  const D = window.CAFE;
  const rows = D.rows;
  const I = { Date: 0, Day: 1, Category: 2, Item: 3, Size: 4, Units: 5, Revenue: 6, COGS: 7, Profit: 8, Payment: 9, Staff: 10, Customers: 11 };
  const ALL = '__all__';
  const C = { navy: '#1B3A5C', navy2: '#3B6FB5', green: '#2E7D32', orange: '#E65100', teal: '#00796B', purple: '#6A4FA3', gold: '#C77700', gray: '#78909C' };
  const PALETTE = ['#1B3A5C', '#E65100', '#2E7D32', '#3B6FB5', '#C77700', '#00796B', '#6A4FA3', '#78909C'];
  const usd = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

  const I18N = {
    ar: {
      appTitle: 'لوحة تحليل أداء الكافيه', appSub: '3 أشهر من العمليات + المخزون | 1,044 معاملة', liveBadge: 'تفاعلي', langToggle: 'English',
      kRev: 'إجمالي الإيرادات', kRevNote: 'revenue', kUnits: 'الوحدات المباعة', kUnitsNote: 'units', kProfit: 'صافي الربح', kProfitNote: 'profit', kMargin: 'هامش الربح', kMarginNote: 'margin',
      fMonth: 'الشهر', fCategory: 'الفئة', fItem: 'الصنف', fSize: 'المقاس', fPayment: 'طريقة الدفع', fStaff: 'الموظف',
      all: 'الكل', reset: 'إعادة الضبط',
      chTrend: 'الاتجاه اليومي للإيرادات', chCategory: 'الإيرادات حسب الفئة', chItem: 'الإيرادات حسب الصنف',
      chPayment: 'حسب طريقة الدفع', chSize: 'الوحدات حسب المقاس', chStaff: 'الإيرادات حسب الموظف',
      sRev: 'الإيرادات', sUnits: 'الوحدات', sProfit: 'الربح',
      ctTitle: 'تواصل معنا', ctSub: 'نرحب باستفساراتك — رسالة مباشرة أو واتساب، وسنرد خلال 24 ساعة.',
      ctName: 'الاسم', ctEmail: 'بريدك الإلكتروني', ctMsg: 'رسالتك...', ctSend: 'إرسال الرسالة', ctAlt: 'أو تواصل مباشرة عبر واتساب', ctWa: 'راسلنا على واتساب',
      stSending: 'جارٍ الإرسال...', stOk: 'شكرًا لك! تم استلام رسالتك وسنرد عليك قريبًا.', stErr: 'تعذّر الإرسال. حاول مرة أخرى أو تواصل عبر واتساب.', stAct: 'يرجى تفعيل استقبال البريد أولًا (رابط التفعيل وصل لبريدك).',
      footNote: 'أُعدّت هذه اللوحة من بيانات تشغيل الكافيه — اضغط على أي عمود/شريحة للتصفية، واضغط مجددًا للإلغاء.'
    },
    en: {
      appTitle: 'Cafe Performance Dashboard', appSub: '3 months of operations + inventory | 1,044 transactions', liveBadge: 'Interactive', langToggle: 'العربية',
      kRev: 'Total Revenue', kRevNote: 'revenue', kUnits: 'Units Sold', kUnitsNote: 'units', kProfit: 'Net Profit', kProfitNote: 'profit', kMargin: 'Profit Margin', kMarginNote: 'margin',
      fMonth: 'Month', fCategory: 'Category', fItem: 'Item', fSize: 'Size', fPayment: 'Payment', fStaff: 'Staff',
      all: 'All', reset: 'Reset',
      chTrend: 'Daily Revenue Trend', chCategory: 'Revenue by Category', chItem: 'Revenue by Item',
      chPayment: 'Revenue by Payment Method', chSize: 'Units by Size', chStaff: 'Revenue by Staff',
      sRev: 'Revenue', sUnits: 'Units', sProfit: 'Profit',
      ctTitle: 'Get in touch', ctSub: 'Questions? Message us directly or via WhatsApp — we reply within 24 hours.',
      ctName: 'Your name', ctEmail: 'Your email', ctMsg: 'Your message...', ctSend: 'Send message', ctAlt: 'Or message us directly on WhatsApp', ctWa: 'Chat on WhatsApp',
      stSending: 'Sending...', stOk: 'Thank you! Your message was received — we will reply soon.', stErr: 'Could not send. Please try again or reach us on WhatsApp.', stAct: 'Please activate email receiving first (check your inbox for the confirmation link).',
      footNote: 'Built from cafe operations data — click any bar/slice to filter, click again to clear.'
    }
  };

  let lang = 'ar';
  const t = k => I18N[lang][k] || k;

  const filters = {};
  const dims = ['Category', 'Item', 'Size', 'Payment', 'Staff'];
  ['Month'].concat(dims).forEach(d => filters[d] = ALL);

  const values = {};
  dims.forEach(d => values[d] = D.meta[d.toLowerCase()] || Array.from(new Set(rows.map(r => r[I[d]]))).sort());
  values.Month = D.meta.months;

  const dimLabels = { Month: 'fMonth', Category: 'fCategory', Item: 'fItem', Size: 'fSize', Payment: 'fPayment', Staff: 'fStaff' };

  function match(r) {
    if (filters.Month !== ALL && r[I.Date].slice(0, 7) !== filters.Month) return false;
    for (const d of dims) if (filters[d] !== ALL && r[I[d]] !== filters[d]) return false;
    return true;
  }
  function filtered() { return rows.filter(match); }
  function totals(list) {
    let units = 0, sales = 0, profit = 0;
    for (const r of list) { units += r[I.Units]; sales += r[I.Revenue]; profit += r[I.Profit]; }
    return { units, sales, profit, margin: sales ? profit / sales : 0 };
  }
  function groupBy(list, key) {
    const m = {};
    for (const r of list) m[r[I[key]]] = (m[r[I[key]]] || 0) + r[I.Revenue];
    return Object.entries(m).map(([name, v]) => ({ name, v }));
  }
  function groupUnits(list, key) {
    const m = {};
    for (const r of list) m[r[I[key]]] = (m[r[I[key]]] || 0) + r[I.Units];
    return Object.entries(m).map(([name, v]) => ({ name, v }));
  }

  const charts = {};
  const mk = id => { const c = echarts.init(document.getElementById(id)); charts[id] = c; return c; };

  function clickDim(key) {
    return function (params) {
      if (!params || params.componentType !== 'series' || params.name == null) return;
      const v = params.name;
      filters[key] = (filters[key] === v) ? ALL : v;
      refresh();
    };
  }

  function renderKPI(list) {
    const tt = totals(list);
    const cards = [
      { label: t('kRev'), value: '$' + usd.format(tt.sales), note: t('kRevNote') },
      { label: t('kUnits'), value: usd.format(tt.units), note: t('kUnitsNote') },
      { label: t('kProfit'), value: '$' + usd.format(tt.profit), note: t('kProfitNote') },
      { label: t('kMargin'), value: (tt.margin * 100).toFixed(1) + '%', note: t('kMarginNote') }
    ];
    document.getElementById('kpis').innerHTML = cards.map(c =>
      `<div class="kpi"><div class="k-label">${c.label}</div><div class="k-value">${c.value}</div><div class="k-note">${c.note}</div></div>`).join('');
  }

  function renderTrend(list) {
    const m = {};
    for (const r of list) {
      const k = r[I.Date];
      m[k] = m[k] || { s: 0, p: 0 };
      m[k].s += r[I.Revenue]; m[k].p += r[I.Profit];
    }
    const keys = Object.keys(m).sort();
    const ch = mk('ch-trend');
    ch.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: '#6B7A90' } },
      grid: { left: 10, right: 10, top: 30, bottom: 6, containLabel: true },
      xAxis: { type: 'category', data: keys, axisLabel: { color: '#6B7A90', rotate: 55 }, axisLine: { lineStyle: { color: '#C9D4E0' } } },
      yAxis: { type: 'value', axisLabel: { color: '#6B7A90', formatter: v => '$' + usd.format(v) }, splitLine: { lineStyle: { color: '#EDF1F7' } } },
      series: [
        { name: t('sRev'), type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: keys.map(k => m[k].s), areaStyle: { opacity: .12 }, itemStyle: { color: C.navy }, lineStyle: { width: 3 } },
        { name: t('sProfit'), type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: keys.map(k => m[k].p), itemStyle: { color: C.orange }, lineStyle: { width: 2.5 } }
      ]
    }, true);
    ch.off('click');
    ch.on('click', clickDim('Month'));
  }

  function barChart(id, data, key, horizontal, unitKey) {
    const ch = mk(id);
    const list = data.slice().sort((a, b) => b.v - a.v);
    const names = list.map(x => x.name);
    const vals = list.map(x => x.v);
    const opt = {
      textStyle: { fontFamily: 'inherit' },
      grid: { left: 8, right: 8, top: 10, bottom: 8, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: v => '$' + usd.format(v || 0) },
      xAxis: { axisLine: { lineStyle: { color: '#C9D4E0' } }, axisLabel: { color: '#6B7A90' } },
      yAxis: { axisLabel: { color: '#6B7A90' }, splitLine: { lineStyle: { color: '#EDF1F7' } } },
      color: [C.navy],
      series: []
    };
    const label = { show: true, formatter: p => '$' + usd.format(p.value), color: '#6B7A90' };
    if (horizontal) {
      opt.xAxis.type = 'value';
      opt.yAxis.type = 'category'; opt.yAxis.data = names; opt.yAxis.inverse = true;
      opt.series.push({ type: 'bar', data: vals, barWidth: '58%', itemStyle: { color: C.navy, borderRadius: [0, 5, 5, 0] }, label: Object.assign({}, label, { position: 'right' }) });
    } else {
      opt.xAxis.type = 'category'; opt.xAxis.data = names;
      opt.yAxis.type = 'value';
      opt.series.push({ type: 'bar', data: vals, barWidth: '52%', itemStyle: { color: C.navy, borderRadius: [5, 5, 0, 0] }, label: Object.assign({}, label, { position: 'top' }) });
    }
    ch.setOption(opt, true);
    ch.off('click');
    ch.on('click', clickDim(key));
  }

  function renderCategory(list) { barChart('ch-category', groupBy(list, 'Category'), 'Category'); }
  function renderPayment(list) { barChart('ch-payment', groupBy(list, 'Payment'), 'Payment'); }
  function renderItem(list) { barChart('ch-item', groupBy(list, 'Item'), 'Item', true); }
  function renderStaff(list) { barChart('ch-staff', groupBy(list, 'Staff'), 'Staff'); }

  function renderSize(list) {
    const g = groupUnits(list, 'Size').sort((a, b) => b.v - a.v);
    const ch = mk('ch-size');
    ch.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#6B7A90' } },
      series: [{
        type: 'pie', radius: ['42%', '70%'], center: ['50%', '46%'],
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c}', fontSize: 10, color: '#4A5A6E' },
        data: g.map((x, i) => ({ name: x.name, value: x.v, itemStyle: { color: PALETTE[i % PALETTE.length] } }))
      }]
    }, true);
    ch.off('click');
    ch.on('click', clickDim('Size'));
  }

  function buildFilters() {
    const host = document.getElementById('filters');
    ['Month'].concat(dims).forEach(key => {
      const g = document.createElement('div');
      g.className = 'fgroup';
      const l = document.createElement('label');
      l.textContent = t(dimLabels[key]);
      l.dataset.i18n = dimLabels[key];
      const s = document.createElement('select');
      const opt = document.createElement('option');
      opt.value = ALL; opt.textContent = t('all');
      s.appendChild(opt);
      values[key].forEach(v => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v;
        s.appendChild(o);
      });
      s.dataset.key = key;
      s.addEventListener('change', () => { filters[key] = s.value; refresh(); });
      g.appendChild(l); g.appendChild(s);
      host.appendChild(g);
    });
    const btn = document.createElement('button');
    btn.className = 'btn-reset';
    btn.textContent = t('reset');
    btn.dataset.i18n = 'reset';
    btn.addEventListener('click', () => { Object.keys(filters).forEach(k => filters[k] = ALL); refresh(); });
    host.appendChild(btn);
  }

  function syncSelects() {
    document.querySelectorAll('#filters select').forEach(s => { s.value = filters[s.dataset.key]; });
  }

  function renderChips() {
    const host = document.getElementById('activeRow');
    const active = Object.keys(filters).filter(k => filters[k] !== ALL);
    if (!active.length) { host.innerHTML = ''; return; }
    host.innerHTML = active.map(k =>
      `<span class="chip">${t(dimLabels[k])}: <b>${filters[k]}</b><button class="x" data-k="${k}">✕</button></span>`).join('');
    host.querySelectorAll('.x').forEach(b => b.addEventListener('click', () => { filters[b.dataset.k] = ALL; refresh(); }));
  }

  function markActiveCards() {
    document.querySelectorAll('.card').forEach(c => c.classList.toggle('hot', filters[c.dataset.dim] !== ALL));
  }

  function refresh() {
    const list = filtered();
    renderKPI(list);
    renderTrend(list);
    renderCategory(list);
    renderItem(list);
    renderPayment(list);
    renderSize(list);
    renderStaff(list);
    syncSelects();
    renderChips();
    markActiveCards();
  }

  /* ---------- i18n ---------- */
  function applyI18n() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    document.querySelectorAll('#filters select option[value="__all__"]').forEach(o => { o.textContent = t('all'); });
    const tg = document.getElementById('langToggle');
    if (tg) tg.textContent = t('langToggle');
    document.title = t('appTitle') + ' — Dashboard';
  }

  document.getElementById('langToggle').addEventListener('click', () => {
    lang = lang === 'ar' ? 'en' : 'ar';
    applyI18n();
    refresh();
  });

  /* ---------- Contact form (FormSubmit) ---------- */
  function initContact() {
    const form = document.getElementById('cform');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      const st = form.querySelector('.form-status');
      const fd = new FormData(form);
      fd.set('_subject', form.dataset.subject);
      fd.set('_captcha', 'false');
      fd.set('_template', 'table');
      fd.set('_honey', '');
      fd.append('_page', window.location.href);
      btn.disabled = true;
      st.className = 'form-status sending';
      st.textContent = t('stSending');
      try {
        const res = await fetch(form.action, { method: 'POST', body: fd, headers: { 'Accept': 'application/json' } });
        const json = await res.json();
        if (json.success === 'true' || json.success === true) {
          st.className = 'form-status ok';
          st.textContent = t('stOk');
          form.reset();
        } else if (json.success === 'false') {
          st.className = 'form-status err';
          st.textContent = t('stAct');
        } else {
          st.className = 'form-status err';
          st.textContent = t('stErr');
        }
      } catch (err) {
        st.className = 'form-status err';
        st.textContent = t('stErr');
      }
      btn.disabled = false;
    });
  }

  buildFilters();
  initContact();
  applyI18n();
  window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
  window.__charts = charts;
  refresh();
})();
