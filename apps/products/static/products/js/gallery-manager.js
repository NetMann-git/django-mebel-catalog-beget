/* Sequential, original-byte uploads. All server mutations remain CSRF protected. */
(() => {
  'use strict';
  const root = document.getElementById('product-gallery');
  if (!root) return;
  const cap = JSON.parse(document.getElementById('gallery-upload-limits').textContent);
  const input = root.querySelector('[data-files]');
  const queue = root.querySelector('[data-queue]');
  const summary = root.querySelector('[data-summary]');
  const status = root.querySelector('[data-status]');
  const start = root.querySelector('[data-start]');
  const retry = root.querySelector('[data-retry]');
  const refresh = root.querySelector('[data-refresh]');
  const progress = root.querySelector('[data-progress]');
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const mb = bytes => (bytes / 1048576).toFixed(1) + ' МБ';
  const collator = new Intl.Collator('ru', {numeric: true, sensitivity: 'base'});
  let items = [], busy = false, editorDirty = false;
  (document.getElementById('product-form') || document.getElementById('product_form'))?.addEventListener('input', () => { editorDirty = true; });
  root.querySelector('.car-gallery__saved-form').addEventListener('submit', event => {
    if (editorDirty && !confirm('В полях изделия есть несохранённые изменения. Продолжить без их сохранения?')) event.preventDefault();
  });
  root.querySelector('[data-limits]').textContent = `За один выбор: до ${cap.files} файлов, по ${mb(cap.bytes)}, всего до ${mb(cap.total)}. До ${cap.pixels / 1000000} Мп на фото; в галерее — до ${cap.gallery} фото.`;
  function updateSummary() {
    summary.textContent = `Выбрано: ${items.length}. Общий размер: ${mb(items.reduce((n, i) => n + i.file.size, 0))}.`;
  }
  function show(item, text, error = false) {
    item.label.textContent = text;
    item.label.className = error ? 'car-gallery__error' : 'car-gallery__ok';
  }
  function selectionError() {
    if (items.length > cap.files) return `Выберите не более ${cap.files} файлов.`;
    if (items.reduce((n, i) => n + i.file.size, 0) > cap.total) return `Общий размер должен быть не более ${mb(cap.total)}.`;
    return '';
  }
  input.addEventListener('change', () => {
    if (busy) return;
    items.forEach(i => URL.revokeObjectURL(i.url));
    queue.replaceChildren();
    items = Array.from(input.files).sort((a,b) => collator.compare(a.name,b.name)).map(file => {
      const item = {file, state: 'pending', url: URL.createObjectURL(file)};
      const card = document.createElement('article'); card.className = 'car-gallery__card';
      const img = document.createElement('img'); img.src = item.url; img.alt = file.name;
      const title = document.createElement('span'); title.textContent = file.name;
      const size = document.createElement('small'); size.textContent = mb(file.size);
      item.label = document.createElement('small'); item.label.textContent = 'Ожидает загрузки';
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Убрать из очереди';
      remove.addEventListener('click', () => {
        if (busy) return;
        items = items.filter(i => i !== item); URL.revokeObjectURL(item.url); card.remove();
        updateSummary(); status.textContent = selectionError();
      });
      card.append(img,title,size,item.label,remove); queue.append(card);
      if (!file.size || file.size > cap.bytes) {
        item.state = 'error'; show(item, `Файл пуст или больше ${mb(cap.bytes)}.`, true);
      }
      return item;
    });
    updateSummary(); status.textContent = selectionError(); retry.hidden = true; progress.value = 0;
  });
  async function post(url, data) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(url, {method: 'POST', body: data, credentials: 'same-origin',
        headers: {'X-CSRFToken': csrf}, signal: controller.signal});
      if (response.redirected) throw new Error('Сессия закончилась или нет доступа. Войдите заново.');
      if (!(response.headers.get('content-type') || '').includes('application/json')) {
        if (response.status === 413) throw new Error('Хостинг отклонил размер файла (413). Уменьшите файл или измените лимит на сервере.');
        if (response.status === 403) throw new Error('Проверка безопасности не пройдена. Обновите страницу и войдите заново.');
        throw new Error(`Сервер не смог обработать запрос (${response.status}). Повторите попытку.`);
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Не удалось загрузить фотографию.');
      return result;
    } catch(error) {
      if (error.name === 'AbortError') throw new Error('Истекло время ожидания. Повторите попытку: дубли будут пропущены.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function fields(values) {
    const data = new FormData(); Object.entries(values).forEach(([k,v]) => data.append(k,v)); return data;
  }
  function setBusy(value) {
    busy = value;
    root.querySelectorAll('button, input').forEach(el => { el.disabled = value; });
  }
  async function run() {
    if (busy) return;
    if (selectionError()) { status.textContent = selectionError(); return; }
    const pending = items.filter(i => !['added','duplicate'].includes(i.state));
    if (!pending.length) { status.textContent = 'Выберите фотографии для загрузки.'; return; }
    if (!window.crypto?.subtle) {
      status.textContent = 'Для проверки файлов откройте сайт через HTTPS (или localhost при локальной разработке).'; return;
    }
    setBusy(true); retry.hidden = true;
    try {
      const ready = [];
      for (const item of pending) {
        try {
          if (!item.file.size || item.file.size > cap.bytes) throw new Error(`Файл пуст или больше ${mb(cap.bytes)}.`);
          show(item, 'Проверка контрольной суммы…');
          const digest = await crypto.subtle.digest('SHA-256', await item.file.arrayBuffer());
          item.sha256 = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,'0')).join('');
          ready.push(item);
        } catch(error) { item.state = 'error'; show(item, error.message, true); }
      }
      if (!ready.length) return;
      status.textContent = 'Проверка ранее сохранённых фотографий…';
      let prepared = false;
      while (!prepared) {
        prepared = (await post(root.dataset.prepare, fields({action: 'hashes'}))).ready;
      }
      const batch = await post(root.dataset.prepare, fields({files: JSON.stringify(ready.map(i => ({size: i.file.size, sha256: i.sha256})))}));
      progress.max = ready.length; progress.value = 0;
      for (let index = 0; index < ready.length; index++) {
        const item = ready[index];
        show(item, `Загрузка ${index + 1} из ${ready.length}…`);
        try {
          const data = fields({token: batch.token, index}); data.append('image', item.file, item.file.name);
          const result = await post(root.dataset.upload, data);
          item.state = result.status;
          show(item, result.status === 'added' ? 'Добавлено' : 'Пропущено: такое фото уже есть');
        } catch(error) { item.state = 'error'; show(item, error.message || 'Ошибка сети. Повторите попытку.', true); }
        progress.value = index + 1;
      }
    } catch(error) {
      pending.filter(i => !['added','duplicate'].includes(i.state)).forEach(i => {
        i.state = 'error'; show(i, error.message || 'Ошибка сети.', true);
      });
    } finally {
      setBusy(false);
      const count = state => items.filter(i => i.state === state).length;
      status.textContent = `Добавлено: ${count('added')}, пропущено дублей: ${count('duplicate')}, ошибок: ${count('error')}.`;
      retry.hidden = !count('error');
      refresh.hidden = !items.some(i => ['added','duplicate'].includes(i.state));
    }
  }
  start.addEventListener('click', run); retry.addEventListener('click', run);
  refresh.addEventListener('click', event => {
    event.preventDefault();
    if (!editorDirty || confirm('В полях изделия есть несохранённые изменения. Обновить страницу без их сохранения?')) location.reload();
  });
  root.querySelectorAll('[data-delete-photo]').forEach(button => button.addEventListener('click', event => {
    if (!confirm('Удалить эту фотографию?')) event.preventDefault();
  }));
  window.addEventListener('beforeunload', event => {
    if (busy) { event.preventDefault(); event.returnValue = ''; }
  });
})();
