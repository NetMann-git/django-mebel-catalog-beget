// apps/appointments/static/appointments/js/modal_window.js
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('appointment-modal');
    const modalBody = document.getElementById('appointment-modal-body');

    if (!modal) return;

    function openModal(productId) {
        modal.style.cssText = 'display: flex !important; align-items: center; justify-content: center; position: fixed; inset: 0; z-index: 100000; background: rgba(0,0,0,0.6); padding: 20px; box-sizing: border-box;';
        document.body.style.overflow = 'hidden';

        modalBody.innerHTML = '<div class="modal-loader">Загрузка...</div>';

        const url = productId ? `/appointments/form/${productId}/` : '/appointments/form/';
        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => {
            if (!response.ok) throw new Error('Ошибка загрузки формы');
            return response.text();
        })
        .then(html => {
            modalBody.innerHTML = html;
            const form = modalBody.querySelector('form');
            if (form) {
                form.addEventListener('submit', handleFormSubmit);
            }
            const closeBtn = modal.querySelector('.modal-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', closeModal);
            }
        })
        .catch(error => {
            modalBody.innerHTML = '<p>Ошибка загрузки формы. Попробуйте позже.</p>';
        });
    }

    const productBtn = document.getElementById('open-appointment-modal');
    if (productBtn) {
        productBtn.addEventListener('click', function() {
            const productId = this.dataset.productId;
            openModal(productId);
        });
    }

    const headerBtn = document.getElementById('open-appointment-modal-header');
    if (headerBtn) {
        headerBtn.addEventListener('click', function() {
            openModal(null);
        });
    }

    // Поддержка дополнительных кнопок записи (hero, CTA)
    document.querySelectorAll('.appointment-trigger').forEach(btn => {
        btn.addEventListener('click', function() {
            openModal(null);
        });
    });

    function closeModal() {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }

    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            closeModal();
        }
    });

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modalBody.innerHTML = `
                    <div class="appointment-success">
                        <h2>✅ Спасибо!</h2>
                        <p>${data.message || 'Ваша заявка на консультацию отправлена. Мы свяжемся с вами для согласования даты и времени.'}</p>
                        <button class="btn" onclick="document.querySelector('.modal-close').click()">Закрыть</button>
                    </div>
                `;
            } else {
                if (data.errors) {
                    let errorHtml = '<div class="form-errors"><ul>';
                    for (const [field, errors] of Object.entries(data.errors)) {
                        errors.forEach(err => {
                            errorHtml += `<li>${field}: ${err}</li>`;
                        });
                    }
                    errorHtml += '</ul></div>';
                    const formElement = modalBody.querySelector('form');
                    if (formElement) {
                        formElement.insertAdjacentHTML('beforebegin', errorHtml);
                    }
                }
            }
        })
        .catch(error => {
            modalBody.innerHTML = '<p>Произошла ошибка. Попробуйте позже.</p>';
        });
    }

    document.addEventListener('change', function(e) {
        const dateInput = e.target.closest('.date-picker');
        if (!dateInput) return;

        const date = dateInput.value;
        const form = dateInput.closest('form');
        if (!form) return;

        const timeSelect = form.querySelector('.time-select');
        const loading = form.querySelector('#slots-loading');
        const errorDiv = form.querySelector('#slots-error');

        if (!timeSelect) return;

        if (!date) {
            timeSelect.innerHTML = '<option value="">Сначала выберите дату</option>';
            timeSelect.disabled = true;
            return;
        }

        if (loading) loading.style.display = 'block';
        if (errorDiv) errorDiv.style.display = 'none';
        timeSelect.disabled = true;
        timeSelect.innerHTML = '<option value="">Загрузка...</option>';

        fetch(`/appointments/slots/${date}/`)
            .then(response => response.json())
            .then(data => {
                if (loading) loading.style.display = 'none';
                timeSelect.innerHTML = '';

                if (data.error) {
                    if (errorDiv) {
                        errorDiv.textContent = data.error;
                        errorDiv.style.display = 'block';
                    }
                    timeSelect.disabled = true;
                    return;
                }

                const slots = data.slots || [];
                const availableSlots = slots.filter(s => s.available);

                if (availableSlots.length === 0) {
                    timeSelect.innerHTML = '<option value="">Нет свободного времени</option>';
                    timeSelect.disabled = true;
                    return;
                }

                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'Выберите время';
                timeSelect.appendChild(defaultOption);

                availableSlots.forEach(slot => {
                    const option = document.createElement('option');
                    option.value = slot.time;
                    option.textContent = slot.time;
                    timeSelect.appendChild(option);
                });

                timeSelect.disabled = false;
            })
            .catch(error => {
                if (loading) loading.style.display = 'none';
                if (errorDiv) {
                    errorDiv.textContent = 'Ошибка загрузки времени. Попробуйте позже.';
                    errorDiv.style.display = 'block';
                }
                timeSelect.disabled = true;
            });
    });
});