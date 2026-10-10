/* ==========================================================================
   LOFI PROTOTYPE RUNTIME  ·  低保真原型交互引擎
   职责：页面路由（可跳转/可返回）、弹窗、抽屉、下拉、标签页、表单校验、
        加载态、Toast、折叠、全选、排序。全部通过 data-* 属性声明，无需写 JS。
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------- 0. 工具 ------------------------- */
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);
  const ICONS = {
    check: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8.5l3.2 3.2L13 5"/></svg>',
    warn:  '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.8v4M8 11.2v.6"/></svg>'
  };

  /* ------------------------- 1. 路由：页面跳转 ------------------------- */
  const Router = {
    home: null,
    stack: [],
    init() {
      const first = $('.page');
      this.home = first ? first.id : null;
      window.addEventListener('hashchange', () => this.render());
      this.render();
    },
    go(id, { push = true } = {}) {
      const cur = this.current();
      if (cur && push && cur !== id) this.stack.push(cur);
      location.hash = '#/' + id;
    },
    back() {
      if (this.stack.length) { location.hash = '#/' + this.stack.pop(); }
      else if (history.length > 1) { history.back(); }
    },
    current() {
      const m = location.hash.match(/^#\/(.+)$/);
      if (m && document.getElementById(m[1])) return m[1];
      return $('.page.is-active') ? $('.page.is-active').id : this.home;
    },
    render() {
      const id = this.current();
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;
      $$('.page').forEach(p => p.classList.toggle('is-active', p === target));

      // 更新浏览器模拟栏
      $$('.browser-bar').forEach(bar => {
        const t = bar.querySelector('.bb-title');
        const u = bar.querySelector('.bb-url');
        const pid = bar.querySelector('.bb-id');
        const backBtn = bar.querySelector('[data-back]');
        if (t) t.textContent = target.dataset.title || '未命名页面';
        if (u) u.textContent = location.origin + location.pathname + '#/' + id;
        if (pid) pid.textContent = target.dataset.pid || '';
        if (backBtn) backBtn.disabled = this.stack.length === 0;
      });

      // 同步导航高亮 + 流程图当前节点
      $$('.nav-item, .tabbar .tb').forEach(n => {
        n.classList.toggle('is-active', n.dataset.goto === id);
      });
      $$('.flow-node').forEach(n => n.classList.toggle('is-current', n.dataset.goto === id));

      // 关闭层级浮层
      closeAllOverlays();
      const scroller = target.closest('.app') || window;
      if (scroller.scrollTo) scroller.scrollTo({ top: 0 });
    }
  };

  /* ------------------------- 2. 浮层：弹窗 / 抽屉 ------------------------- */
  function openOverlay(el) {
    if (!el) return;
    if (el.classList.contains('mask')) el.classList.add('is-open');
    else el.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    const f = el.querySelector('[autofocus],input,textarea,select');
    if (f) setTimeout(() => f.focus(), 60);
  }
  function closeOverlay(el) {
    if (!el) return;
    el.classList.remove('is-open');
    if (!document.querySelector('.mask.is-open, .drawer.is-open')) document.body.style.overflow = '';
  }
  function closeAllOverlays() {
    $$('.mask.is-open, .drawer.is-open, .sidebar.is-open, .scrim.is-open').forEach(closeOverlay);
  }

  /* ------------------------- 3. Toast ------------------------- */
  function toast(msg, type) {
    let host = $('.toast-host');
    if (!host) { host = document.createElement('div'); host.className = 'toast-host'; document.body.appendChild(host); }
    const t = document.createElement('div');
    t.className = 'toast' + (type === 'error' ? ' is-error' : '');
    t.innerHTML = (type === 'error' ? ICONS.warn : '') + '<span></span>';
    t.querySelector('span').textContent = msg;
    host.appendChild(t);
    setTimeout(() => { t.classList.add('is-out'); setTimeout(() => t.remove(), 220); }, 2200);
  }
  window.LofiToast = toast;

  /* ------------------------- 4. 自定义下拉 ------------------------- */
  function bindSelect(sel) {
    const trigger = sel.querySelector('.select-trigger');
    const valEl   = sel.querySelector('.sel-val');
    const options = $$('.opt', sel);
    if (!trigger) return;
    if (!trigger.hasAttribute('tabindex')) trigger.setAttribute('tabindex', '0');
    if (trigger.tagName === 'BUTTON') return;

    const toggle = (open) => {
      const willOpen = open === undefined ? !sel.classList.contains('open') : open;
      $$('.select.open').forEach(s => { if (s !== sel) s.classList.remove('open'); });
      sel.classList.toggle('open', willOpen);
    };
    on(trigger, 'click', e => { e.stopPropagation(); toggle(); });
    on(trigger, 'keydown', e => {
      if (['Enter', ' '].includes(e.key)) { e.preventDefault(); toggle(); }
      if (e.key === 'Escape') toggle(false);
    });
    options.forEach(opt => {
      on(opt, 'click', e => {
        e.stopPropagation();
        if (opt.classList.contains('is-disabled')) return;
        options.forEach(o => o.classList.remove('is-selected'));
        opt.classList.add('is-selected');
        if (valEl) {
          valEl.textContent = opt.dataset.label || opt.textContent.trim();
          valEl.classList.remove('is-placeholder');
        }
        toggle(false);
        sel.dispatchEvent(new CustomEvent('select:change', { bubbles: true, detail: { value: opt.dataset.value } }));
        const act = sel.dataset.onchange;
        if (act) toast(act);
      });
    });
    if (valEl && valEl.textContent.trim() === (sel.dataset.placeholder || '请选择')) {
      valEl.classList.add('is-placeholder');
    }
  }

  /* ------------------------- 5. 表单校验 ------------------------- */

  /* 错误文案元素：.field 内部找；label.check 场景取紧随其后的兄弟 .field-error */
  function errElOf(field) {
    if (!field) return null;
    if (field.classList.contains('check')) {
      const n = field.nextElementSibling;
      return n && n.classList.contains('field-error') ? n : null;
    }
    return field.querySelector('.field-error');
  }

  /* 校验字段容器：优先 .field；复选框 / 单选可直接写在 label.check 上，
     此时以该 label 为容器，并自动在其后补一个 .field-error 承载错误文案。 */
  function fieldOf(ctrl) {
    const field = ctrl.closest('.field');
    if (field) return field;
    const lab = ctrl.closest('label.check');
    if (!lab) return null;
    const n = lab.nextElementSibling;
    if (!(n && n.classList.contains('field-error'))) {
      const err = document.createElement('span');
      err.className = 'field-error check-error';
      lab.insertAdjacentElement('afterend', err);
    }
    return lab;
  }

  function validateForm(form) {
    let ok = true, firstBad = null;
    $$('[data-required]', form).forEach(ctrl => {
      const field = fieldOf(ctrl);
      if (!field) return;
      let val = '';
      if (ctrl.classList.contains('select')) {
        const sel = ctrl.querySelector('.opt.is-selected');
        val = sel && !sel.classList.contains('is-placeholder') ? (sel.dataset.value || '') : '';
      } else if (ctrl.type === 'checkbox' || ctrl.type === 'radio') {
        val = ctrl.checked ? '1' : '';
      } else {
        val = (ctrl.value || '').trim();
      }
      const bad = val === '';
      field.classList.toggle('has-error', bad);
      const errEl = errElOf(field);
      if (errEl && bad) {
        if (!errEl.querySelector('svg')) errEl.insertAdjacentHTML('afterbegin', ICONS.warn);
        if (!errEl.dataset.msg) errEl.dataset.msg = '此项为必填';
        if (!errEl.textContent.trim()) errEl.insertAdjacentHTML('beforeend', '<span>此项为必填</span>');
      }
      if (bad && !firstBad) firstBad = ctrl;
      if (bad) ok = false;
    });
    // 自定义规则
    $$('[data-rule]', form).forEach(ctrl => {
      const field = fieldOf(ctrl);
      if (!field) return;
      const rule = ctrl.dataset.rule;
      const v = (ctrl.value || '').trim();
      let bad = false, msg = ctrl.dataset.ruleMsg || '格式不正确';
      if (rule === 'phone' && v) bad = !/^1[3-9]\d{9}$/.test(v);
      if (rule === 'email' && v) bad = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
      if (rule.startsWith('min:')) bad = v.length < parseInt(rule.split(':')[1], 10);
      if (rule.startsWith('max:')) bad = v.length > parseInt(rule.split(':')[1], 10);
      field.classList.toggle('has-error', bad);
      const errEl = errElOf(field);
      if (bad && errEl) {
        errEl.innerHTML = ICONS.warn + '<span>' + msg + '</span>';
        if (!firstBad) firstBad = ctrl;
      }
      if (bad) ok = false;
    });
    if (firstBad) {
      firstBad.scrollIntoView({ block: 'center', behavior: 'smooth' });
      setTimeout(() => firstBad.focus && firstBad.focus(), 120);
    }
    return ok;
  }

  /* ------------------------- 6. 事件委托（全局） ------------------------- */
  document.addEventListener('click', (e) => {
    const t = e.target;

    /* —— 页面跳转 —— */
    const gotoEl = t.closest('[data-goto]');
    if (gotoEl && !gotoEl.closest('.flow')) {
      // 表格整行可跳转时，行内的复选框/按钮/链接优先，不触发整行跳转
      if (gotoEl.tagName === 'TR' && t.closest('input, label, button, a, .select')) { /* 交给下方处理器 */ }
      else {
        e.preventDefault();
        Router.go(gotoEl.dataset.goto, { push: gotoEl.dataset.push !== 'false' });
        return;
      }
    }
    if (t.closest('.flow')) {
      const fn = t.closest('.flow-node');
      if (fn && fn.dataset.goto) { e.preventDefault(); Router.go(fn.dataset.goto); }
      return;
    }

    /* —— 返回 —— */
    if (t.closest('[data-back]')) { e.preventDefault(); Router.back(); return; }

    /* —— 打开弹窗 / 抽屉 —— */
    const openBtn = t.closest('[data-modal-open],[data-drawer-open],[data-sidebar-open]');
    if (openBtn) {
      e.preventDefault();
      const sel = openBtn.dataset.modalOpen || openBtn.dataset.drawerOpen || openBtn.dataset.sidebarOpen;
      openOverlay(document.querySelector(sel));
      return;
    }
    /* —— 关闭 —— */
    const closeBtn = t.closest('[data-close]');
    if (closeBtn) {
      e.preventDefault();
      closeOverlay(closeBtn.closest('.mask, .drawer, .sidebar, .scrim'));
      return;
    }
    /* —— 点遮罩关闭 —— */
    if (t.classList.contains('mask') || t.classList.contains('scrim')) { closeOverlay(t); return; }

    /* —— 标签页 —— */
    const tab = t.closest('[data-tab]');
    if (tab) {
      e.preventDefault();
      if (tab.classList.contains('is-disabled')) return;
      const group = tab.closest('[data-tab-group]') || tab.parentElement.parentElement;
      $$('[data-tab]', group).forEach(x => x.classList.remove('is-active'));
      tab.classList.add('is-active');
      const panes = $$('[data-tab-pane]', group);
      panes.forEach(p => p.classList.toggle('is-active', p.dataset.tabPane === tab.dataset.tab));
      return;
    }

    /* —— 折叠 / 展开 —— */
    const colBtn = t.closest('[data-collapse]');
    if (colBtn) {
      e.preventDefault();
      const target = document.querySelector(colBtn.dataset.collapse);
      const expanded = colBtn.getAttribute('aria-expanded') === 'true';
      colBtn.setAttribute('aria-expanded', String(!expanded));
      if (target) target.classList.toggle('is-open', !expanded);
      return;
    }

    /* —— 模拟加载：按钮 loading —— */
    const loadBtn = t.closest('[data-loading]');
    // 校验表单内的提交按钮交给 submit 流程统一处理，避免阻断校验
    if (loadBtn && loadBtn.type === 'submit' && loadBtn.closest('form[data-validate]')) { /* noop */ }
    else if (loadBtn) {
      e.preventDefault();
      if (loadBtn.classList.contains('is-loading')) return;
      const ms = parseInt(loadBtn.dataset.loading, 10) || 1200;
      loadBtn.classList.add('is-loading');
      loadBtn.disabled = true;
      setTimeout(() => {
        loadBtn.classList.remove('is-loading');
        loadBtn.disabled = false;
        const done = loadBtn.dataset.loadingDone;
        if (done) toast(done);
        const goAfter = loadBtn.dataset.loadingGoto;
        if (goAfter) Router.go(goAfter);
      }, ms);
      return;
    }

    /* —— 区块加载态（骨架屏） —— */
    const skelBtn = t.closest('[data-skeleton]');
    if (skelBtn) {
      e.preventDefault();
      const target = document.querySelector(skelBtn.dataset.skeleton);
      if (!target) return;
      const ms = parseInt(skelBtn.dataset.skeletonMs, 10) || 1400;
      target.classList.add('is-loading-rel');
      let mask = target.querySelector(':scope > .loading-mask');
      if (!mask) {
        mask = document.createElement('div');
        mask.className = 'loading-mask';
        mask.innerHTML = '<div class="spinner"></div><span>加载中…</span>';
        target.appendChild(mask);
      }
      setTimeout(() => { target.classList.remove('is-loading-rel'); }, ms);
      return;
    }

    /* —— Toast —— */
    const toastBtn = t.closest('[data-toast]');
    if (toastBtn) {
      e.preventDefault();
      toast(toastBtn.dataset.toast, toastBtn.dataset.toastType);
      return;
    }

    /* —— 表格行选中 —— */
    const tr = t.closest('tr[data-selectable]');
    if (tr && !t.closest('button, a, input, .select')) {
      $$('tr[data-selectable]', tr.closest('tbody')).forEach(x => x.classList.remove('is-selected'));
      tr.classList.add('is-selected');
    }

    /* —— 全选 —— */
    if (t.closest('[data-check-all]')) {
      e.preventDefault();
      const scope = t.closest('[data-check-scope]') || document;
      const boxes = $$('input[type=checkbox]', scope).filter(b => !b.disabled && !b.dataset.checkAll);
      const allChecked = boxes.every(b => b.checked);
      boxes.forEach(b => { b.checked = !allChecked; b.dispatchEvent(new Event('change', { bubbles: true })); });
      const master = t.closest('[data-check-all]').querySelector('input[type=checkbox]') || t;
      if (master.type === 'checkbox') { master.checked = !allChecked; master.indeterminate = false; }
      return;
    }

    /* —— 排序（仅视觉） —— */
    const sortTh = t.closest('th.sortable');
    if (sortTh) {
      const table = sortTh.closest('table');
      $$('th.sortable', table).forEach(th => { if (th !== sortTh) { th.classList.remove('is-sorted'); const s = th.querySelector('.sort'); if (s) s.textContent = '↕'; } });
      sortTh.classList.add('is-sorted');
      const s = sortTh.querySelector('.sort');
      if (s) s.textContent = s.textContent === '↑' ? '↓' : '↑';
      return;
    }

    /* —— 收起其它下拉 —— */
    if (!t.closest('.select')) $$('.select.open').forEach(s => s.classList.remove('open'));
  });

  /* ------------------------- 7. 表单提交拦截 ------------------------- */
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!form.matches('form[data-validate]')) return;
    e.preventDefault();
    const ok = validateForm(form);
    if (!ok) { toast('表单存在 ' + form.querySelectorAll('.field.has-error, .check.has-error').length + ' 项校验错误，请检查', 'error'); return; }

    const submitter = e.submitter || document.activeElement;
    const ms = submitter && submitter.dataset && submitter.dataset.loading ? parseInt(submitter.dataset.loading, 10) : 0;
    if (ms && submitter) { submitter.classList.add('is-loading'); submitter.disabled = true; }

    setTimeout(() => {
      if (ms && submitter) { submitter.classList.remove('is-loading'); submitter.disabled = false; }
      toast(form.dataset.success || '提交成功');
      const go = form.dataset.successGoto;
      if (go) Router.go(go);
      const close = form.dataset.successClose;
      if (close) closeOverlay(document.querySelector(close));
    }, ms || 0);
  });

  /* 输入即清除错误态 */
  document.addEventListener('input', (e) => {
    const f = e.target.closest('.field.has-error');
    if (f && e.target.type !== 'checkbox' && e.target.type !== 'radio') f.classList.remove('has-error');
  });
  document.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox' || e.target.type === 'radio') {
      const f = e.target.closest('.field.has-error') || e.target.closest('label.check.has-error');
      if (!f) return;
      f.classList.remove('has-error');
      const err = errElOf(f);
      if (err) { err.textContent = ''; delete err.dataset.msg; }
    }
  });

  /* ------------------------- 8. 键盘 ------------------------- */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllOverlays();
    if (e.key === 'Backspace' && e.target === document.body) { e.preventDefault(); Router.back(); }
  });

  /* ------------------------- 9. 舞台：视口切换 ------------------------- */
  function bindStage() {
    const stage = $('.stage');
    if (!stage) return;
    $$('.stage-bar .seg button').forEach(btn => {
      on(btn, 'click', () => {
        $$('.stage-bar .seg button').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const w = btn.dataset.w;
        stage.style.setProperty('--vp-w', w === 'full' ? '100%' : w + 'px');
      });
    });
  }

  /* ------------------------- 10. 图标注入 ------------------------- */
  const SVG_ICONS = {
    menu:    '<path d="M3 4.5h10M3 8h10M3 11.5h10"/>',
    search:  '<circle cx="7" cy="7" r="4"/><path d="M10.2 10.2L13.5 13.5"/>',
    close:   '<path d="M4 4l8 8M12 4l-8 8"/>',
    chevronDown: '<path d="M4 6.5l4 4 4-4"/>',
    chevronRight:'<path d="M6.5 4l4 4-4 4"/>',
    chevronLeft: '<path d="M9.5 4l-4 4 4 4"/>',
    arrowRight:  '<path d="M3 8h10M9.5 4.5L13 8l-3.5 3.5"/>',
    arrowLeft:   '<path d="M13 8H3M6.5 4.5L3 8l3.5 3.5"/>',
    plus:    '<path d="M8 3.5v9M3.5 8h9"/>',
    minus:   '<path d="M3.5 8h9"/>',
    check:   '<path d="M3 8.5l3.2 3.2L13 5"/>',
    trash:   '<path d="M3.5 4.5h9M6.5 4.5V3h3v1.5M5 4.5l.6 8.5h4.8l.6-8.5"/>',
    edit:    '<path d="M11.2 2.8l2 2-7 7-2.6.6.6-2.6 7-7z"/>',
    user:    '<circle cx="8" cy="5.5" r="2.5"/><path d="M3.5 13.5c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5"/>',
    home:    '<path d="M2.5 7.5L8 3l5.5 4.5v5h-3.5v-3.5h-4v3.5H2.5v-5z"/>',
    bell:    '<path d="M4 7a4 4 0 018 0v3l1.2 2H2.8L4 10V7z"/><path d="M6.5 12.5a1.5 1.5 0 003 0"/>',
    filter:  '<path d="M2.5 4h11l-4.2 5v4l-2.6-1.4V9L2.5 4z"/>',
    more:    '<circle cx="4" cy="8" r="1"/><circle cx="8" cy="8" r="1"/><circle cx="12" cy="8" r="1"/>',
    eye:     '<path d="M1.5 8S4 4 8 4s6.5 4 6.5 4-2.5 4-6.5 4S1.5 8 1.5 8z"/><circle cx="8" cy="8" r="1.8"/>',
    upload:  '<path d="M8 11V3.5M5 6.5L8 3.5l3 3"/><path d="M3 10.5v2h10v-2"/>',
    download:'<path d="M8 3v7.5M5 7.5L8 10.5l3-3"/><path d="M3 10.5v2h10v-2"/>',
    calendar:'<rect x="2.5" y="3.5" width="11" height="10" rx="1"/><path d="M2.5 6.5h11M5.5 2v2.4M10.5 2v2.4"/>',
    image:   '<rect x="2.5" y="3" width="11" height="10" rx="1"/><circle cx="6" cy="6.5" r="1"/><path d="M3 11.5l3.5-3.5 3 3 2-2 2.5 2.5"/>',
    warn:    '<circle cx="8" cy="8" r="6.2"/><path d="M8 4.8v4M8 11.2v.6"/>',
    info:    '<circle cx="8" cy="8" r="6.2"/><path d="M8 7.5v3.5M8 5v.6"/>',
    star:    '<path d="M8 2.5l1.8 3.7 4 .6-2.9 2.8.7 4-3.6-1.9-3.6 1.9.7-4L2.2 6.8l4-.6L8 2.5z"/>',
    clock:   '<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.8"/>',
    setting: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1"/>',
    logout:  '<path d="M9.5 4.5H4v7h5.5"/><path d="M10.5 8h-5M9.5 5.5l2.5 2.5-2.5 2.5"/>',
    inbox:   '<path d="M2.5 9l1-5h9l1 5v3.5h-11V9z"/><path d="M2.5 9h3l1 1.5h3l1-1.5h3"/>',
    list:    '<path d="M5.5 4.5h8M5.5 8h8M5.5 11.5h8M3 4.5h.01M3 8h.01M3 11.5h.01"/>',
    grid:    '<rect x="3" y="3" width="4.2" height="4.2" rx="1"/><rect x="8.8" y="3" width="4.2" height="4.2" rx="1"/><rect x="3" y="8.8" width="4.2" height="4.2" rx="1"/><rect x="8.8" y="8.8" width="4.2" height="4.2" rx="1"/>',
    refresh: '<path d="M12.5 8a4.5 4.5 0 11-1.6-3.4"/><path d="M12.8 3.2v2.6h-2.6"/>'
  };
  function icon(name, size) {
    const s = size || 16;
    const p = SVG_ICONS[name] || '';
    return '<svg class="ico" width="' + s + '" height="' + s + '" viewBox="0 0 16 16" fill="none" ' +
      'stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">' + p + '</svg>';
  }
  window.LofiIcon = icon;

  function injectIcons() {
    $$('[data-icon]').forEach(el => {
      if (el.dataset.iconDone) return;
      el.insertAdjacentHTML('afterbegin', icon(el.dataset.icon, parseInt(el.dataset.iconSize, 10) || 16));
      el.dataset.iconDone = '1';
    });
  }

  /* ------------------------- 11. 启动 ------------------------- */
  function boot() {
    injectIcons();
    $$('.select').forEach(bindSelect);
    bindStage();
    Router.init();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  window.Lofi = { Router, toast, icon, openOverlay, closeOverlay, closeAllOverlays };
})();
