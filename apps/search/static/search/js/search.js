// apps/search/static/search/js/search.js
// шаг 25: reuse the original suggestion widget, including replaced catalog filters.
const initializedSearchInputs = new WeakSet();
const closeSmartSearch = new WeakMap();
document.addEventListener('click', event => {
    document.querySelectorAll('[data-smart-search], #search-container').forEach(root => {
        if (!root.contains(event.target)) closeSmartSearch.get(root)?.();
    });
});
function initializeSmartSearch() {
 document.querySelectorAll('[data-smart-search], #search-container').forEach(root => {
    const searchInput = root.querySelector('[data-smart-search-input], #search-input');
    const resultsContainer = root.querySelector('[data-search-results], #search-results');
    if (!searchInput || !resultsContainer || initializedSearchInputs.has(searchInput)) return;
    initializedSearchInputs.add(searchInput);
    let revision = 0;
    let controller;
    const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
    const show = () => { resultsContainer.style.display = 'block'; searchInput.setAttribute('aria-expanded', 'true'); };
    const hide = () => { revision++; clearTimeout(debounceTimer); if (controller) controller.abort(); resultsContainer.style.display = 'none'; searchInput.setAttribute('aria-expanded', 'false'); };
    closeSmartSearch.set(root, hide);
    async function load(url, render) {
        const ownRevision = ++revision;
        if (controller) controller.abort();
        controller = new AbortController();
        try {
            const response = await fetch(url, {signal: controller.signal, headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            if (ownRevision === revision && searchInput.isConnected && document.activeElement === searchInput) render(data);
        } catch (error) { if (error.name !== 'AbortError' && ownRevision === revision) hide(); }
    }

    const priceFormatter = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2});
    const formatPrice = value => {
        const number = Number(value);
        return Number.isFinite(number) ? priceFormatter.format(number) : '';
    };

    let debounceTimer;

    // Показываем популярные запросы при фокусе (если поле пустое)
    searchInput.addEventListener('focus', function() {
        const query = this.value.trim();
        if (query.length === 0) {
            load('/search/popular/', data => renderPopular(data.popular));
        } else if (query.length >= 2) {
            load(`/search/suggest/?q=${encodeURIComponent(query)}`, data => renderResults(data.results, query));
        }
    });

    // Поиск по вводу (с debounce)
    searchInput.addEventListener('input', function() {
        hide();
        const query = this.value.trim();

        if (query.length < 2) {
            hide();
            return;
        }

        debounceTimer = setTimeout(() => {
            load(`/search/suggest/?q=${encodeURIComponent(query)}`, data => renderResults(data.results, query));
        }, 250);
    });

    function renderResults(results, query) {
        if (!results || results.length === 0) {
            resultsContainer.innerHTML = '<div class="search-empty">Ничего не найдено</div>';
            show();
            return;
        }

        let html = '<ul class="search-dropdown">';
        results.forEach(item => {
            if (item.type === 'product') {
                html += `
                    <li class="search-item product" data-url="${escapeHTML(item.url)}">
                        <div class="search-item-image">
                            ${item.image ? `<img src="${escapeHTML(item.image)}" alt="${escapeHTML(item.title)}">` : ''}
                        </div>
                        <div class="search-item-content">
                            <div class="search-item-title">${highlightText(item.title, query)}</div>
                            <div class="search-item-meta">
                                ${item.price ? `<span class="price">${formatPrice(item.price)} ${escapeHTML(item.currency)}</span>` : ''}
                                ${item.category ? `<span class="category">${escapeHTML(item.category)}</span>` : ''}
                            </div>
                            ${item.badges && item.badges.length ? `<div class="search-item-badges">${item.badges.map(b => `<span class="badge badge-${escapeHTML(b.slug)}">${escapeHTML(b.title)}</span>`).join('')}</div>` : ''}
                        </div>
                    </li>
                `;
            } else if (item.type === 'attribute') {
                html += `
                    <li class="search-item attribute" data-url="${escapeHTML(item.url)}">
                        <div class="search-item-image">
                            ${item.image ? `<img src="${escapeHTML(item.image)}" alt="${escapeHTML(item.product_title)}">` : ''}
                        </div>
                        <div class="search-item-content">
                            <div class="search-item-title">${highlightText(item.title, query)}</div>
                            <div class="search-item-meta">
                                ${item.price ? `<span class="price">${formatPrice(item.price)} ${escapeHTML(item.currency)}</span>` : ''}
                                <span class="search-item-type">Характеристика</span>
                            </div>
                        </div>
                    </li>
                `;
            } else {
                html += `
                    <li class="search-item category" data-url="${escapeHTML(item.url)}">
                        <span class="search-item-title">${highlightText(item.title, query)}</span>
                        <span class="search-item-type">${item.type === 'category' ? 'Категория' : 'Бейдж'}</span>
                    </li>
                `;
            }
        });
        html += '</ul>';
        resultsContainer.innerHTML = html;
        show();
    }

    function renderPopular(queries) {
        if (!queries || queries.length === 0) {
            hide();
            return;
        }
        let html = '<ul class="search-dropdown popular">';
        queries.forEach(q => {
            html += `<li class="search-item popular" data-query="${escapeHTML(q)}">🔍 ${escapeHTML(q)}</li>`;
        });
        html += '</ul>';
        resultsContainer.innerHTML = html;
        show();
    }

    // Подсветка совпадений
    function highlightText(text, query) {
        text = String(text ?? '');
        if (!query) return escapeHTML(text);
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.split(regex).map((part, index) => index % 2 ? '<mark>' + escapeHTML(part) + '</mark>' : escapeHTML(part)).join('');
    }

    // Клик по результату – переход по ссылке
    root.addEventListener('click', function(e) {
        const item = e.target.closest('.search-item');
        if (item && !resultsContainer.contains(item)) return;
        if (item) {
            if (item.classList.contains('popular')) {
                const query = item.dataset.query;
                window.location.href = `/catalog/?q=${encodeURIComponent(query)}`;
                return;
            }
            if (item.dataset.url) {
                window.location.href = item.dataset.url;
            }
        } else if (!root.contains(e.target)) {
            hide();
        }
    });

    // Клавиатура (↓ ↑ Enter Esc)
    searchInput.addEventListener('keydown', function(e) {
        if (resultsContainer.style.display === 'none') return;
        if (e.key === 'Escape') {
            hide();
            searchInput.blur();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = resultsContainer.querySelectorAll('.search-item');
            if (!items.length) return;
            let currentIndex = Array.from(items).findIndex(el => el.classList.contains('active'));
            if (e.key === 'ArrowDown') {
                if (currentIndex < items.length - 1) currentIndex++;
                else currentIndex = 0;
            } else {
                if (currentIndex > 0) currentIndex--;
                else currentIndex = items.length - 1;
            }
            items.forEach(el => el.classList.remove('active'));
            items[currentIndex].classList.add('active');
            items[currentIndex].scrollIntoView({ block: 'nearest' });
        }
        if (e.key === 'Enter') {
            const active = resultsContainer.querySelector('.search-item.active');
            if (active) {
                e.preventDefault();
                if (active.classList.contains('popular')) {
                    const query = active.dataset.query;
                    window.location.href = `/catalog/?q=${encodeURIComponent(query)}`;
                } else if (active.dataset.url) {
                    window.location.href = active.dataset.url;
                }
            }
        }
    });
 });
}
document.addEventListener('DOMContentLoaded', initializeSmartSearch);
document.addEventListener('catalog:updated', initializeSmartSearch);
