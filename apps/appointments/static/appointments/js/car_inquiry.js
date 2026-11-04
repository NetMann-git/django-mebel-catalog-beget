document.addEventListener('DOMContentLoaded', () => {
    const triggers = document.querySelectorAll('.car-inquiry__trigger');
    const modal = document.getElementById('car-inquiry-modal');
    const content = document.getElementById('car-inquiry-content');
    if (!triggers.length || !modal || !content) return;

    const closeButton = modal.querySelector('.car-inquiry__close');
    const headers = { 'X-Requested-With': 'XMLHttpRequest' };
    let activeTrigger = null;
    let requestVersion = 0;
    let loadController = null;
    let previousOverflow = '';

    function isCurrent(version, form = null) {
        return !modal.hidden && version === requestVersion && (!form || content.contains(form));
    }

    function close() {
        requestVersion += 1;
        loadController?.abort();
        loadController = null;
        modal.hidden = true;
        document.body.style.overflow = previousOverflow;
        const returnFocus = activeTrigger;
        activeTrigger = null;
        returnFocus?.focus();
    }

    triggers.forEach((trigger) => {
        trigger.addEventListener('click', async (event) => {
            event.preventDefault();
            const version = ++requestVersion;
            loadController?.abort();
            const controller = typeof AbortController === 'function' ? new AbortController() : null;
            loadController = controller;
            activeTrigger = trigger;
            if (modal.hidden) previousOverflow = document.body.style.overflow;
            modal.hidden = false;
            document.body.style.overflow = 'hidden';
            content.textContent = 'Загружаем форму…';
            closeButton.focus();
            try {
                const response = await fetch(trigger.href, { headers, ...(controller ? { signal: controller.signal } : {}) });
                if (!response.ok) throw new Error('Не удалось загрузить форму');
                const html = await response.text();
                if (!isCurrent(version)) return;
                content.innerHTML = html;
                content.querySelector('input:not([type="hidden"])')?.focus();
            } catch (error) {
                if (!isCurrent(version)) return;
                content.textContent = 'Форма временно недоступна. Попробуйте открыть её отдельно.';
                const link = document.createElement('a');
                link.href = trigger.href;
                link.textContent = 'Открыть форму';
                content.append(link);
            } finally {
                if (loadController === controller) loadController = null;
            }
        });
    });

    closeButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) close();
    });
    document.addEventListener('keydown', (event) => {
        if (modal.hidden) return;
        if (event.key === 'Escape') close();
        if (event.key === 'Tab') {
            const controls = Array.from(modal.querySelectorAll('button:not([disabled]), a[href], input:not([type="hidden"]):not([name="website"]), textarea, select'));
            const first = controls[0], last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
    });

    content.addEventListener('submit', async (event) => {
        if (!event.target.matches('.car-inquiry__form')) return;
        event.preventDefault();
        const form = event.target;
        const version = requestVersion;
        const button = form.querySelector('[type="submit"]');
        button.disabled = true;
        try {
            const data = new FormData(form);
            const currentToken = typeof getCookie === 'function' ? getCookie('csrftoken') : null;
            if (currentToken) data.set('csrfmiddlewaretoken', currentToken);
            const response = await fetch(form.action, {
                method: 'POST',
                headers,
                body: data,
            });
            if (response.status === 400) {
                const html = await response.text();
                if (!isCurrent(version, form)) return;
                content.innerHTML = html;
                return;
            }
            if (!response.ok) throw new Error('Не удалось отправить запрос');
            const result = await response.json();
            if (!result.success) throw new Error('Не удалось отправить запрос');
            // POST не отменяется при закрытии: заявка уже могла сохраниться.
            if (!isCurrent(version, form)) return;
            content.innerHTML = '';
            const title = document.createElement('h2');
            title.id = 'car-inquiry-title';
            title.textContent = 'Спасибо!';
            const message = document.createElement('p');
            message.textContent = result.message || 'Заявка получена. Менеджер свяжется с вами.';
            content.append(title, message);
            closeButton.focus();
        } catch (error) {
            if (!isCurrent(version, form)) return;
            button.disabled = false;
            let errorText = form.querySelector('.car-inquiry__error--submit');
            if (!errorText) {
                errorText = document.createElement('p');
                errorText.className = 'car-inquiry__error car-inquiry__error--submit';
                form.append(errorText);
            }
            errorText.textContent = 'Не удалось отправить запрос. Попробуйте ещё раз.';
        }
    });
});
