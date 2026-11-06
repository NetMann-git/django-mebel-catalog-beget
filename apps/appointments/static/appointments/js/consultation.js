/* Standalone consultation form: select only times returned by the schedule. */
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-consultation-form]');
    if (!form) return;
    const date = form.querySelector('[name="date"]');
    const time = form.querySelector('[name="time"]');
    const status = form.querySelector('[data-slot-status]');
    let requestNumber = 0;
    async function loadSlots() {
        const current = ++requestNumber;
        const selected = time.value;
        time.disabled = true;
        time.replaceChildren(new Option('Сначала выберите дату', ''));
        status.textContent = '';
        if (!date.value) return;
        status.textContent = 'Загрузка свободного времени…';
        try {
            const response = await fetch(`/appointments/slots/${encodeURIComponent(date.value)}/`);
            const data = await response.json();
            if (current !== requestNumber) return;
            if (!response.ok || data.error) {
                status.textContent = data.error || 'Не удалось загрузить время. Выберите дату ещё раз.';
                return;
            }
            const slots = (data.slots || []).filter(slot => slot.available);
            time.replaceChildren(new Option('Выберите время', ''));
            for (const slot of slots) time.add(new Option(slot.time, slot.time));
            if (slots.some(slot => slot.time === selected)) time.value = selected;
            time.disabled = !slots.length;
            status.textContent = slots.length ? '' : 'На выбранную дату свободного времени нет.';
        } catch (_) {
            if (current === requestNumber) status.textContent = 'Не удалось загрузить время. Проверьте соединение и выберите дату ещё раз.';
        }
    }
    date.addEventListener('change', loadSlots);
    loadSlots();
});
