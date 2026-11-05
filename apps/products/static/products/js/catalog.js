/* One controller owns filter replacement and pagination to avoid stale results. */
document.addEventListener('DOMContentLoaded', () => {
    'use strict';
    const workspace = document.getElementById('catalog-workspace');
    if (!workspace || !window.fetch || !window.AbortController) return;
    const status = document.getElementById('catalog-request-status');
    const error = document.getElementById('catalog-request-error');
    const fallback = document.getElementById('catalog-fallback');
    let appliedURL = new URL(location.href);
    let controller = null;
    let revision = 0;
    let loading = false;
    let observer = null;
    let retry = null;

    // Open by default on every screen; preserve an explicit manual choice in this visit.
    let filterPanelOpen = true;
    function updatePanel() {
        const panel = workspace.querySelector('#catalog-filter-panel');
        if (!panel) return;
        if (workspace.querySelector('.catalog-filter-errors')) filterPanelOpen = true;
        panel.open = filterPanelOpen;
    }
    workspace.addEventListener('toggle', event => {
        const panel = workspace.querySelector('#catalog-filter-panel');
        if (event.target === panel) filterPanelOpen = panel.open;
    }, true);

    function initialize() {
        document.dispatchEvent(new Event('catalog:updated'));
        updatePanel();
        const form = workspace.querySelector('#catalog-filter-form');
        const brand = form.elements.brand;
        const model = form.elements.model;
        // Мебельный фильтр не содержит селектов марки/модели.
        if (brand && model && model.options) {
            const options = Array.from(model.options, option => option.cloneNode(true));
            function updateModel() {
                const selected = model.value;
                model.replaceChildren(...options.filter(option =>
                    !option.value || option.dataset.brand === brand.value
                ).map(option => option.cloneNode(true)));
                model.value = Array.from(model.options).some(option => option.value === selected) ? selected : '';
                model.disabled = !brand.value;
                model.options[0].textContent = brand.value ? 'Все модели' : 'Сначала выберите марку';
            }
            brand.addEventListener('change', updateModel);
            updateModel();
        }
        workspace.querySelectorAll('.pagination, .catalog-sort-submit').forEach(node => { node.hidden = true; });
        const container = workspace.querySelector('#catalog-products-container');
        const more = workspace.querySelector('#load-more-btn');
        more.style.display = container.dataset.hasNext === 'true' ? 'block' : 'none';
        if ('IntersectionObserver' in window) {
            observer = new IntersectionObserver(entries => {
                if (entries.some(entry => entry.isIntersecting)) loadMore();
            }, {rootMargin: '150px'});
            observer.observe(workspace.querySelector('#catalog-load-sentinel'));
        }
    }

    async function request(url, append = false, historyMode = 'push') {
        if (append && loading) return;
        if (controller) controller.abort();
        if (observer) observer.disconnect();
        const ownRevision = ++revision;
        controller = new AbortController();
        loading = true;
        error.hidden = true;
        workspace.setAttribute('aria-busy', 'true');
        status.textContent = append ? 'Загружаем ещё изделия…' : 'Обновляем подборку…';
        const intent = {url: url.href, append, historyMode};
        try {
            const response = await fetch(url, {
                signal: controller.signal,
                headers: append ? {'X-Requested-With': 'XMLHttpRequest'} : {'X-Catalog-Mode': 'replace'},
            });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = append ? await response.json() : await response.text();
            if (ownRevision !== revision) return;
            if (append) {
                if (typeof data.html !== 'string' || typeof data.has_next !== 'boolean') throw new Error('Invalid response');
                const container = workspace.querySelector('#catalog-products-container');
                container.querySelector('.dress-grid').insertAdjacentHTML('beforeend', data.html);
                container.dataset.hasNext = String(data.has_next);
                container.dataset.nextPage = data.next_page || '';
                workspace.querySelector('#load-more-btn').style.display = data.has_next ? 'block' : 'none';
                status.textContent = 'Изделия загружены.';
                if (data.has_next && observer) observer.observe(workspace.querySelector('#catalog-load-sentinel'));
            } else {
                const fragment = document.createElement('template');
                fragment.innerHTML = data;
                if (!fragment.content.querySelector('#catalog-filter-form') || !fragment.content.querySelector('#catalog-results')) throw new Error('Invalid response');
                workspace.replaceChildren(fragment.content);
                appliedURL = new URL(url);
                if (historyMode === 'push' && location.href !== url.href) history.pushState(null, '', url);
                initialize();
                status.textContent = workspace.querySelector('.catalog-count').textContent.trim();
                workspace.querySelector('#catalog-results').focus({preventScroll: true});
            }
            retry = null;
        } catch (problem) {
            if (problem.name !== 'AbortError' && ownRevision === revision) {
                retry = intent;
                fallback.href = url.href;
                error.hidden = false;
                status.textContent = '';
            }
        } finally {
            if (ownRevision === revision) {
                loading = false;
                workspace.removeAttribute('aria-busy');
            }
        }
    }

    function loadMore() {
        const container = workspace.querySelector('#catalog-products-container');
        if (loading || container.dataset.hasNext !== 'true') return;
        const url = new URL(appliedURL);
        url.searchParams.set('page', container.dataset.nextPage);
        request(url, true);
    }

    workspace.addEventListener('submit', event => {
        const form = event.target;
        if (!form.matches('#catalog-filter-form, [data-catalog-sort-form]')) return;
        event.preventDefault();
        const url = new URL(location.pathname, location.origin);
        for (const [key, value] of new FormData(form)) if (String(value).trim()) url.searchParams.set(key, value);
        request(url);
    });
    workspace.addEventListener('change', event => {
        // Brand's own change handler has already cleared an incompatible model.
        const autoSubmit = '[data-catalog-sort-form] select, ' +
            '#catalog-filter-form select[name="brand"], ' +
            '#catalog-filter-form select[name="model"], ' +
            '#catalog-filter-form select[name="year"], ' +
            '#catalog-filter-form select[name="category"]';
        if (event.target.matches(autoSubmit)) event.target.form.requestSubmit();
    });
    workspace.addEventListener('click', event => {
        if (event.target.closest('#load-more-btn')) { loadMore(); return; }
        const link = event.target.closest('.filter-chip, .catalog-filter-reset, .clear-filters, .pagination a');
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
        event.preventDefault();
        request(new URL(link.href));
    });
    document.getElementById('catalog-retry').addEventListener('click', () => {
        if (retry) request(new URL(retry.url), retry.append, retry.historyMode);
    });
    window.addEventListener('popstate', () => request(new URL(location.href), false, 'none'));
    initialize();
});
