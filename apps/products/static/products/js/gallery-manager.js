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
  const conflictRefresh = root.querySelector('[data-conflict-refresh]');
  const progress = root.querySelector('[data-progress]');
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const mb = bytes => (bytes / 1048576).toFixed(1) + ' МБ';
  const collator = new Intl.Collator('ru', {numeric: true, sensitivity: 'base'});
  let items = [], busy = false, editorDirty = false;
  const editorForm = document.getElementById('product-form') || document.getElementById('product_form');
  function markEditorDirty() {
    editorDirty = true;
  }
  editorForm?.addEventListener('input', markEditorDirty);
  editorForm?.addEventListener('change', markEditorDirty);
  const savedForm = root.querySelector('.car-gallery__saved-form');
  const savedPhotos = root.querySelector('[data-saved-photos]');
  const pendingOrder = root.querySelector('[data-pending-order]');
  const pendingMessage = root.querySelector('[data-pending-message]');
  const orderStatus = root.querySelector('[data-order-status]');
  let draggedPhoto = null;
  let leavingGallery = false;
  let orderFields = Array.from(savedPhotos.querySelectorAll('.car-gallery__order input'));
  let originalCards = Array.from(savedPhotos.querySelectorAll('[data-saved-photo]'));
  const orderChanged = () => {
    const currentCards = savedPhotos.querySelectorAll('[data-saved-photo]');
    return originalCards.some((card, index) => card !== currentCards[index])
      || orderFields.some(field => field.value !== field.defaultValue);
  };
  const orderHint = 'Порядок изменён. Нажмите «Сохранить порядок фото».';

  function showOrderStatus() {
    const changed = orderChanged();
    if (pendingOrder) pendingOrder.hidden = !changed;
    if (orderStatus) orderStatus.textContent = changed ? orderHint : '';
  }

  root.querySelector('[data-reset-order]').addEventListener('click', () => {
    if (busy || !orderChanged()) return;
    savedPhotos.append(...originalCards);
    orderFields.forEach(field => { field.value = field.defaultValue; });
    pendingMessage.textContent = 'Порядок фото сохраняется отдельно.';
    showOrderStatus();
    orderStatus.textContent = 'Восстановлен последний сохранённый порядок фотографий.';
    savedForm.querySelector('[data-save-order]').focus();
  });

  savedPhotos.addEventListener('input', showOrderStatus);

  function updateOrder() {
    const cards = savedPhotos.querySelectorAll('[data-saved-photo]');
    cards.forEach((card, index) => {
      card.querySelector('.car-gallery__order input').value = index + 1;
    });
    showOrderStatus();
  }

  function enablePhotoControls() {
    savedPhotos.querySelectorAll('[data-move-controls]').forEach(controls => {
      controls.hidden = false;
    });
    savedPhotos.querySelectorAll('[data-drag-photo]').forEach(handle => {
      handle.hidden = false;
      handle.draggable = true;
      handle.addEventListener('dragstart', event => {
        if (busy) { event.preventDefault(); return; }
        draggedPhoto = handle.closest('[data-saved-photo]');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', 'photo-order');
        draggedPhoto.classList.add('car-gallery__card--dragging');
      });
      handle.addEventListener('dragend', () => {
        draggedPhoto?.classList.remove('car-gallery__card--dragging');
        draggedPhoto = null;
      });
    });
  }
  enablePhotoControls();
  savedPhotos.addEventListener('dragover', event => {
    const target = event.target.closest('[data-saved-photo]');
    if (draggedPhoto && target && target !== draggedPhoto) {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
    }
  });
  savedPhotos.addEventListener('drop', event => {
    const target = event.target.closest('[data-saved-photo]');
    if (busy || !draggedPhoto || !target || target === draggedPhoto) return;
    event.preventDefault();
    const cards = Array.from(savedPhotos.querySelectorAll('[data-saved-photo]'));
    if (cards.indexOf(draggedPhoto) < cards.indexOf(target)) {
      target.after(draggedPhoto);
    } else {
      target.before(draggedPhoto);
    }
    updateOrder();
  });
  savedPhotos.addEventListener('click', event => {
    const button = event.target.closest('[data-move-photo]');
    if (!button) return;
    const card = button.closest('[data-saved-photo]');
    if (button.dataset.movePhoto === 'earlier' && card.previousElementSibling?.matches('[data-saved-photo]')) {
      card.previousElementSibling.before(card);
    } else if (button.dataset.movePhoto === 'later' && card.nextElementSibling?.matches('[data-saved-photo]')) {
      card.nextElementSibling.after(card);
    } else {
      return;
    }
    button.focus();
    updateOrder();
  });

  function blockPendingPhotoAction(event) {
    if (!orderChanged()) return false;
    event.preventDefault();
    const message = 'Сначала сохраните порядок фотографий, затем повторите действие.';
    orderStatus.textContent = message;
    alert(message);
    return true;
  }

  savedPhotos.addEventListener('click', event => {
    const action = event.target.closest('[data-photo-action]');
    if (!action || blockPendingPhotoAction(event)) return;
    if (action.hasAttribute('data-delete-photo') && !confirm('Удалить эту фотографию?')) {
      event.preventDefault();
    }
  }, {capture: true});

  editorForm?.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    if (busy) {
      event.preventDefault();
      alert('Дождитесь завершения действия в галерее, затем сохраните товар.');
      return;
    }
    if (blockPendingPhotoAction(event)) return;
    leavingGallery = true;
  });

  savedForm.addEventListener('submit', event => {
    if (busy || event.submitter?.hasAttribute('data-save-order')) {
      event.preventDefault();
      if (!busy) saveOrder();
      return;
    }
    if (event.submitter?.hasAttribute('data-photo-action') && blockPendingPhotoAction(event)) return;
    if (event.submitter?.hasAttribute('data-delete-photo')) {
      event.preventDefault();
      deletePhoto(event.submitter);
      return;
    }
    if (event.submitter?.hasAttribute('data-set-cover')) {
      event.preventDefault();
      saveCover(event.submitter);
      return;
    }
    if (editorDirty && !confirm('В полях изделия есть несохранённые изменения. Продолжить без их сохранения?')) {
      event.preventDefault();
      return;
    }
    leavingGallery = true;
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
  function updateCoverPreview(url) {
    const preview = root.querySelector('[data-cover-preview]');
    const image = preview.querySelector('img');
    if (url) image.src = url;
    else image.removeAttribute('src');
    preview.hidden = !url;
  }

  async function deletePhoto(button) {
    const feedback = root.querySelector('[data-cover-status]');
    const card = button.closest('[data-saved-photo]');
    setBusy(true);
    feedback.textContent = 'Удаляем фотографию…';
    try {
      const result = await post(button.formAction, fields({}), {Accept: 'application/json'});
      if (typeof result.cover_url !== 'string' || !Array.isArray(result.cover_ids)) {
        throw new Error('Сервер не подтвердил удаление.');
      }

      const removedField = card.querySelector('.car-gallery__order input');
      originalCards = originalCards.filter(item => item !== card);
      orderFields = orderFields.filter(field => field !== removedField);
      card.remove();
      updateCoverPreview(result.cover_url);
      originalCards.forEach(item => {
        item.querySelector('[data-cover-badge]').hidden = !result.cover_ids.includes(item.dataset.savedPhoto);
      });
      if (originalCards.length < 2) {
        savedPhotos.querySelectorAll('[data-drag-photo], [data-move-controls]').forEach(control => {
          control.hidden = true;
        });
      }
      if (!originalCards.length) {
        savedPhotos.querySelector('[data-empty-gallery]').hidden = false;
        savedForm.querySelectorAll('[data-save-order]').forEach(control => { control.hidden = true; });
      }
      feedback.textContent = 'Фотография удалена.';
    } catch (error) {
      feedback.textContent = 'Не удалось подтвердить удаление. ' + error.message;
    } finally {
      setBusy(false);
      const nextFocus = card.isConnected ? button :
        savedPhotos.querySelector('[data-delete-photo]') || input;
      nextFocus.focus({preventScroll: true});
    }
  }

  async function saveCover(button) {
    const feedback = root.querySelector('[data-cover-status]');
    const actionUrl = button.formAction;
    setBusy(true);
    feedback.textContent = 'Сохраняем обложку…';
    try {
      const result = await post(actionUrl, fields({}), {Accept: 'application/json'});
      if (!result.cover_url) throw new Error('Сервер не подтвердил смену обложки.');
      updateCoverPreview(result.cover_url);
      const updated = await syncSavedPhotos();
      feedback.textContent = updated ? 'Обложка сохранена.' :
        'Обложка сохранена. Нажмите «Обновить список фотографий», чтобы увидеть изменения.';
    } catch (error) {
      feedback.textContent = 'Не удалось подтвердить смену обложки. ' + error.message;
    } finally {
      setBusy(false);
      const currentButton = Array.from(savedPhotos.querySelectorAll('[data-set-cover]'))
        .find(control => control.formAction === actionUrl);
      (currentButton || input).focus({preventScroll: true});
    }
  }

  async function saveOrder() {
    const data = new FormData(savedForm);
    const baseline = Object.fromEntries(orderFields.map(field => [field.name, field.defaultValue]));
    data.set('order_baseline', JSON.stringify(baseline));
    setBusy(true);
    pendingMessage.textContent = 'Сохраняем порядок фото…';
    orderStatus.textContent = pendingMessage.textContent;
    try {
      const result = await post(savedForm.action, data, {Accept: 'application/json'});
      const cardsByField = new Map(originalCards.map(card => [
        card.querySelector('.car-gallery__order input').name, card,
      ]));
      if (!Array.isArray(result.order) || result.order.length !== cardsByField.size
          || new Set(result.order).size !== cardsByField.size
          || result.order.some(name => !cardsByField.has(name))) {
        throw new Error('Сервер не подтвердил порядок фотографий.');
      }
      originalCards = result.order.map(name => cardsByField.get(name));
      savedPhotos.append(...originalCards);
      orderFields.forEach(field => { field.defaultValue = field.value; });
      showOrderStatus();
      conflictRefresh.hidden = true;
      orderStatus.textContent = 'Порядок фотографий сохранён.';
      pendingMessage.textContent = 'Порядок фото сохраняется отдельно.';
    } catch (error) {
      if (error.status === 409) {
        refresh.hidden = false;
        conflictRefresh.hidden = false;
      }
      const message = 'Не удалось подтвердить сохранение порядка. ' + error.message;
      pendingMessage.textContent = message;
      orderStatus.textContent = message;
    } finally {
      setBusy(false);
      if (!orderChanged()) savedForm.querySelector('[data-save-order]').focus({preventScroll: true});
    }
  }

  async function post(url, data, headers = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(url, {method: 'POST', body: data, credentials: 'same-origin',
        headers: {'X-CSRFToken': csrf, ...headers}, signal: controller.signal});
      if (response.redirected) throw new Error('Сессия закончилась или нет доступа. Войдите заново.');
      if (!(response.headers.get('content-type') || '').includes('application/json')) {
        if (response.status === 413) throw new Error('Хостинг отклонил размер файла (413). Уменьшите файл или измените лимит на сервере.');
        if (response.status === 403) throw new Error('Проверка безопасности не пройдена. Обновите страницу и войдите заново.');
        throw new Error(`Сервер не смог обработать запрос (${response.status}). Повторите попытку.`);
      }
      const result = await response.json();
      if (!response.ok) {
        const error = new Error(result.error || 'Не удалось выполнить действие в галерее.');
        error.status = response.status;
        throw error;
      }
      return result;
    } catch(error) {
      if (error.name === 'AbortError') throw new Error('Истекло время ожидания. Повторите попытку.');
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
  function requireSavedOrder() {
    if (!orderChanged()) return true;
    status.textContent = 'Сначала сохраните порядок фото, затем продолжите.';
    return false;
  }

  async function syncSavedPhotos() {
    const feedback = root.querySelector('[data-sync-status]');
    try {
      const result = await post(root.dataset.prepare, fields({action: 'snapshot'}));
      const template = document.createElement('template');
      if (typeof result.html !== 'string') throw new Error('Некорректный ответ сервера.');
      template.innerHTML = result.html;
      const grid = template.content.querySelector('[data-saved-photos]');
      const gridPreview = template.content.querySelector('[data-cover-preview]');
      if (!grid || !gridPreview) throw new Error('Список фотографий отсутствует в ответе.');

      savedPhotos.replaceChildren(...grid.childNodes);
      updateCoverPreview(gridPreview.querySelector('img').getAttribute('src'));
      originalCards = Array.from(savedPhotos.querySelectorAll('[data-saved-photo]'));
      orderFields = Array.from(savedPhotos.querySelectorAll('.car-gallery__order input'));
      savedForm.querySelectorAll('[data-save-order]').forEach(button => {
        button.hidden = !originalCards.length;
      });
      enablePhotoControls();
      showOrderStatus();
      feedback.textContent = 'Список фотографий обновлён.';
      refresh.hidden = true;
      conflictRefresh.hidden = true;
      return true;
    } catch (error) {
      feedback.textContent = 'Не удалось обновить список фотографий. ' + error.message;
      refresh.hidden = false;
      return false;
    }
  }

  async function run() {
    if (busy || !requireSavedOrder()) return;
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
      const count = state => items.filter(i => i.state === state).length;
      status.textContent = `Добавлено: ${count('added')}, пропущено дублей: ${count('duplicate')}, ошибок: ${count('error')}.`;
      retry.hidden = !count('error');
      try {
        if (count('added') || count('duplicate')) await syncSavedPhotos();
      } finally {
        setBusy(false);
      }
    }
  }
  start.addEventListener('click', run); retry.addEventListener('click', run);
  async function refreshGallery() {
    if (busy) return;
    if (orderChanged() && !confirm('Загрузить сохранённый порядок фото? Ваша несохранённая перестановка будет отменена.')) return;
    setBusy(true);
    try {
      const updated = await syncSavedPhotos();
      if (!updated && orderChanged()) {
        pendingMessage.textContent = 'Список фотографий не обновился. Ваша перестановка осталась в форме.';
      }
    } finally {
      setBusy(false);
    }
  }

  refresh.addEventListener('click', refreshGallery);
  conflictRefresh.addEventListener('click', refreshGallery);
  window.addEventListener('pageshow', () => {
    leavingGallery = false;
    showOrderStatus();
  });
  window.addEventListener('beforeunload', event => {
    if (busy || (!leavingGallery && (editorDirty || orderChanged()))) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
})();
