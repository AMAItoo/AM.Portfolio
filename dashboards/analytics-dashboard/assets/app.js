(function () {
  const D = window.ADIDAS;
  const rows = D.rows;
  const I = { Retailer: 1, Date: 2, Region: 3, State: 4, City: 5, Product: 6, Price: 7, Units: 8, Sales: 9, Profit: 10, Margin: 11, Method: 12 };
  const ALL = '__all__';
  const C = { navy: '#1B3A5C', navy2: '#3B6FB5', green: '#2E7D32', orange: '#E65100', teal: '#00796B', purple: '#6A4FA3', gold: '#C77700', gray: '#78909C' };
  const PALETTE = ['#1B3A5C', '#E65100', '#2E7D32', '#3B6FB5', '#C77700', '#00796B', '#6A4FA3', '#78909C'];
  const usd = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const usdM = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });

  const dims = ['Region', 'Retailer', 'Product', 'Method', 'State'];
  const labels = { Region: 'المنطقة', Retailer: 'المتجر', Product: 'المنتج', Method: 'قناة البيع', State: 'الولاية', Year: 'السنة', Month: 'الشهر' };

  const filters = {};
  ['Year', 'Month'].concat(dims).forEach(d => filters[d] = ALL);

  const values = {};
  dims.forEach(d => values[d] = Array.from(new Set(rows.map(r => r[I[d]]))).sort());
  values.Year = Array.from(new Set(rows.map(r => r[I.Date].slice(0, 4)))).sort();
  values.Month = Array.from(new Set(rows.map(r => r[I.Date].slice(0, 7)))).sort();

  function match(r) {
    if (filters.Year !== ALL && r[I.Date].slice(0, 4) !== filters.Year) return false;
    if (filters.Month !== ALL && r[I.Date].slice(0, 7) !== filters.Month) return false;
    for (const d of dims) if (filters[d] !== ALL && r[I[d]] !== filters[d]) return false;
    return true;
  }
  function filtered() { return rows.filter(match); }
  function totals(list) {
    let units = 0, sales = 0, profit = 0;
    for (const r of list) { units += r[I.Units]; sales += r[I.Sales]; profit += r[I.Profit]; }
    return { units, sales, profit, margin: sales ? profit / sales : 0 };
  }
  function groupBy(list, key) {
    const m = {};
    for (const r of list) m[r[I[key]]] = (m[r[I[key]]] || 0) + r[I.Sales];
    return Object.entries(m).map(([name, v]) => ({ name, v }));
  }

  const charts = {};
  const mk = (el) => {
    const c = echarts.init(el);
    charts[el.id] = c;
    return c;
  };
  const cardEl = { trend: 'c-trend', region: 'c-region', retailer: 'c-retailer', product: 'c-product', method: 'c-method', state: 'c-state' };

  function clickDim(name, key) {
    return function (params) {
      if (!params || params.componentType !== 'series' || params.name == null) return;
      const v = params.name;
      filters[key] = (filters[key] === v) ? ALL : v;
      if (key === 'Month' && filters[key] !== ALL) filters.Year = filters[key].slice(0, 4);
      refresh();
    };
  }

  function baseOption() {
    return {
      textStyle: { fontFamily: 'inherit' },
      grid: { left: 8, right: 8, top: 10, bottom: 8, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: v => '$' + usd.format(v || 0) },
      xAxis: { axisLine: { lineStyle: { color: '#C9D4E0' } }, axisLabel: { color: '#6B7A90' } },
      yAxis: { axisLabel: { color: '#6B7A90' }, splitLine: { lineStyle: { color: '#EDF1F7' } } },
      series: []
    };
  }

  function renderKPI(list) {
    const t = totals(list);
    const cards = [
      { label: 'إجمالي المبيعات', value: '$' + usdM.format(t.sales / 1e6) + 'M', note: 'million' },
      { label: 'الوحدات المباعة', value: usd.format(t.units), note: 'unit' },
      { label: 'الربح التشغيلي', value: '$' + usdM.format(t.profit / 1e6) + 'M', note: 'million' },
      { label: 'هامش الربح', value: (t.margin * 100).toFixed(1) + '%', note: 'operating margin' }
    ];
    document.getElementById('kpis').innerHTML = cards.map(c =>
      `<div class="kpi"><div class="k-label">${c.label}</div><div class="k-value">${c.value}</div><div class="k-note">${c.note}</div></div>`).join('');
  }

  function renderTrend(list) {
    const m = {};
    for (const r of list) {
      const k = r[I.Date].slice(0, 7);
      m[k] = m[k] || { sales: 0, profit: 0 };
      m[k].sales += r[I.Sales]; m[k].profit += r[I.Profit];
    }
    const keys = Object.keys(m).sort();
    const ch = mk(document.getElementById('ch-trend'));
    ch.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: '#6B7A90' } },
      grid: { left: 10, right: 10, top: 30, bottom: 6, containLabel: true },
      xAxis: { type: 'category', data: keys, axisLabel: { color: '#6B7A90', rotate: 40 }, axisLine: { lineStyle: { color: '#C9D4E0' } } },
      yAxis: { type: 'value', axisLabel: { color: '#6B7A90', formatter: v => '$' + usd.format(v / 1e6) + 'M' }, splitLine: { lineStyle: { color: '#EDF1F7' } } },
      series: [
        { name: 'المبيعات', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: keys.map(k => m[k].sales), areaStyle: { opacity: .12 }, itemStyle: { color: C.navy }, lineStyle: { width: 3 } },
        { name: 'الربح', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: keys.map(k => m[k].profit), itemStyle: { color: C.orange }, lineStyle: { width: 2.5 } }
      ]
    }, true);
    ch.off('click');
    ch.on('click', clickDim('Month', 'Month'));
  }

  function barChart(id, data, title, horizontal) {
    const ch = mk(document.getElementById(id));
    const list = data.slice().sort((a, b) => b.v - a.v);
    const names = list.map(x => x.name);
    const vals = list.map(x => x.v);
    const label = { show: true, formatter: p => '$' + usd.format(p.value / 1e6) + 'M', color: '#6B7A90' };
    const opt = baseOption();
    opt.color = [C.navy];
    if (horizontal) {
      opt.xAxis.type = 'value';
      opt.yAxis.type = 'category';
      opt.yAxis.data = names;
      opt.yAxis.inverse = true;
      opt.series.push({ type: 'bar', data: vals, barWidth: '55%', itemStyle: { color: C.navy, borderRadius: [0, 5, 5, 0] }, label: Object.assign({}, label, { position: 'right' }) });
    } else {
      opt.xAxis.type = 'category';
      opt.xAxis.data = names;
      opt.yAxis.type = 'value';
      opt.series.push({ type: 'bar', data: vals, barWidth: '52%', itemStyle: { color: C.navy, borderRadius: [5, 5, 0, 0] }, label: Object.assign({}, label, { position: 'top' }) });
    }
    ch.setOption(opt, true);
    ch.off('click');
    ch.on('click', clickDim(title, title));
  }

  function renderRegion(list) { barChart('ch-region', groupBy(list, 'Region'), 'Region'); }
  function renderRetailer(list) { barChart('ch-retailer', groupBy(list, 'Retailer'), 'Retailer'); }
  function renderMethod(list) { barChart('ch-method', groupBy(list, 'Method'), 'Method'); }
  function renderState(list) { barChart('ch-state', groupBy(list, 'State').slice(0, 10), 'State', true); }

  function renderProduct(list) {
    const g = groupBy(list, 'Product').sort((a, b) => b.v - a.v);
    const ch = mk(document.getElementById('ch-product'));
    ch.setOption({
      tooltip: { trigger: 'item', valueFormatter: v => '$' + usd.format(v) },
      legend: { bottom: 0, textStyle: { color: '#6B7A90', fontSize: 10 } },
      series: [{
        type: 'pie', radius: ['42%', '70%'], center: ['50%', '46%'],
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c}', fontSize: 10, color: '#4A5A6E' },
        data: g.map((x, i) => ({ name: x.name, value: x.v, itemStyle: { color: PALETTE[i % PALETTE.length] } }))
      }]
    }, true);
    ch.off('click');
    ch.on('click', clickDim('Product', 'Product'));
  }

  function buildFilters() {
    const host = document.getElementById('filters');
    const sel = (key) => {
      const g = document.createElement('div');
      g.className = 'fgroup';
      const l = document.createElement('label');
      l.textContent = labels[key];
      const s = document.createElement('select');
      const opt = document.createElement('option');
      opt.value = ALL; opt.textContent = 'الكل';
      s.appendChild(opt);
      values[key].forEach(v => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v;
        s.appendChild(o);
      });
      s.dataset.key = key;
      s.addEventListener('change', () => {
        filters[key] = s.value;
        refresh();
      });
      g.appendChild(l); g.appendChild(s);
      host.appendChild(g);
    };
    ['Year', 'Month'].concat(dims).forEach(sel);
    const btn = document.createElement('button');
    btn.className = 'btn-reset';
    btn.textContent = 'إعادة الضبط';
    btn.addEventListener('click', () => {
      Object.keys(filters).forEach(k => filters[k] = ALL);
      refresh();
    });
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
      `<span class="chip">${labels[k]}: <b>${filters[k]}</b><button class="x" data-k="${k}">✕</button></span>`).join('');
    host.querySelectorAll('.x').forEach(b => b.addEventListener('click', () => {
      filters[b.dataset.k] = ALL;
      refresh();
    }));
  }

  function markActiveCards() {
    document.querySelectorAll('.card').forEach(c => {
      c.classList.toggle('hot', filters[c.dataset.dim] !== ALL);
    });
  }

  function refresh() {
    const list = filtered();
    renderKPI(list);
    renderTrend(list);
    renderRegion(list);
    renderRetailer(list);
    renderProduct(list);
    renderMethod(list);
    renderState(list);
    syncSelects();
    renderChips();
    markActiveCards();
  }

  buildFilters();
  window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
  window.__charts = charts;
  refresh();
})();
