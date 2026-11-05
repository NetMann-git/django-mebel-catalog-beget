// static/products/js/comparison.js

document.addEventListener('DOMContentLoaded', function() {
    const comparisonCounts = document.querySelectorAll('#comparison-count, [data-comparison-count]');
    const emptyMessage = document.getElementById('empty-message');
    const tableWrapper = document.getElementById('comparison-table-wrapper');
    const backLink = document.querySelector('.comparison-back-link');

    function updateComparisonUI(productId, isAdded, count, message) {
        // Обновляем счётчик в шапке
        comparisonCounts.forEach(counter => { counter.textContent = count; });

        // Обновляем кнопку на карточке
        document.querySelectorAll('.compare-btn[data-product-id="' + productId + '"]')
            .forEach(btn => {
                btn.classList.toggle('active', isAdded);
                const label = btn.querySelector('[data-comparison-label]') || btn.querySelector('span');
                if (label) label.textContent = isAdded ? 'Убрать из сравнения' : 'Добавить к сравнению';
                btn.setAttribute('aria-pressed', String(isAdded));
                if (btn.dataset.productTitle) btn.setAttribute('aria-label',
                    (isAdded ? 'Убрать из сравнения: ' : 'Добавить к сравнению: ') + btn.dataset.productTitle);
            });

        // Если мы на странице сравнения — обновляем её
        if (window.location.pathname === '/catalog/comparison/') {
            if (count === 0) {
                // Показываем сообщение о пустом списке
                if (emptyMessage) emptyMessage.style.display = 'block';
                if (tableWrapper) tableWrapper.style.display = 'none';
                if (backLink) backLink.style.display = 'none';
            } else {
                if (emptyMessage) emptyMessage.style.display = 'none';
                if (tableWrapper) tableWrapper.style.display = 'block';
                if (backLink) backLink.style.display = 'block';
                // Обновляем таблицу (перезагружаем страницу для простоты)
                location.reload();
            }
        }

        // Показываем сообщение
        if (message) {
            showMessage(message);
        }
    }

    function showMessage(message) {
        const existing = document.querySelector('.comparison-message');
        if (existing) existing.remove();

        const div = document.createElement('div');
        div.className = 'comparison-message';
        div.style.cssText = 'position:fixed; bottom:20px; right:20px; background:#333; color:#fff; padding:12px 24px; border-radius:8px; z-index:999;';
        div.textContent = message;
        document.body.appendChild(div);

        setTimeout(() => div.remove(), 3000);
    }

    document.addEventListener('click', function(e) {
        const button = e.target.closest('.compare-btn[data-url]');
        if (!button || !button.dataset.url.startsWith('/catalog/comparison/toggle/')) return;
        e.preventDefault();
        const url = button.dataset.url;
        const productId = button.dataset.productId;

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showMessage(data.message || 'Ошибка');
                return;
            }
            updateComparisonUI(productId, data.is_added, data.count, data.message);
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });
});
