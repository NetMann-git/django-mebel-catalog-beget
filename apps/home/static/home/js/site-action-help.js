/* Шаг 62: делегированные подсказки для обычных и AJAX-элементов. */
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        const hint = document.createElement('div');
        hint.id = 'site-action-help';
        hint.className = 'site-action-help';
        hint.setAttribute('role', 'tooltip');
        hint.hidden = true;
        document.body.appendChild(hint);
        let active = null, timer = null, leaveTimer = null, originalTitle = null, origin = null, touchInput = false;
        const watcher = new MutationObserver(function () {
            if (active && !hint.hidden) { hint.textContent = explain(active); position(); }
        });
        const compact = value => String(value || '').replace(/\s+/g, ' ').trim();
        function label(node) {
            return compact(node.getAttribute('aria-label') || compact(node.textContent) || node.value || node.querySelector?.('img')?.getAttribute('alt')).slice(0, 160);
        }
        function explain(node) {
            if (node.dataset.help) return node.dataset.help;
            if (node.matches('.compare-btn')) {
                if (node.matches('.remove-btn')) return 'Убрать это изделие из таблицы сравнения. Само изделие останется в каталоге; его можно добавить снова.';
                return node.classList.contains('active') ?
                    'Убрать это изделие из вашей подборки для сравнения. Другие выбранные изделия сохранятся. Просмотреть таблицу можно по ссылке «К сравнению».' :
                    'Добавить это изделие в подборку для сравнения характеристик с другими вариантами. Затем откройте «К сравнению» или раздел «Сравнение».';
            }
            if (node.matches('.wishlist-btn')) return node.classList.contains('active') ?
                'Удалить это изделие из избранного. Оно останется доступно в каталоге, и вы сможете сохранить его снова.' :
                'Сохранить это изделие в избранном, чтобы вернуться к нему позже. Сохранённые изделия доступны в разделе «Избранное».';
            if (node.matches('.fm-menu-toggle')) return node.getAttribute('aria-expanded') === 'true' ?
                'Закрыть меню разделов сайта. Также его можно закрыть клавишей Escape или выбором раздела.' :
                'Раскрыть меню разделов сайта. Выберите нужную страницу; после перехода меню закроется.';
            if (node.matches('.vote-btn')) return node.dataset.helpful === 'true' ?
                'Отметить этот отзыв как полезный. Ваша оценка помогает другим посетителям ориентироваться в отзывах.' :
                'Отметить, что этот отзыв не был полезен. Это оценка полезности отзыва, а не самого изделия.';
            if (node.matches('.review-image-link,[data-lightbox]')) return 'Открыть фотографию, приложенную к отзыву, чтобы рассмотреть её подробнее.';
            if (node.matches('.image-arrow,.lightbox-prev,.lightbox-next')) return 'Переключить фотографию в галерее изделия. Остальные данные страницы сохранятся.';
            if (node.matches('.scroll-to-top')) return 'Прокрутить текущую страницу к началу. Выбранные фильтры и заполненные поля сохранятся.';
            if (node.matches('.car-inquiry__close,.lightbox-close,.modal-close')) return 'Закрыть это окно и вернуться к странице. Для закрытия также можно использовать Escape, если окно его поддерживает.';
            if (node.matches('.main-image-trigger,.gallery-thumb-button')) return node.matches('.main-image-trigger') ?
                'Открыть увеличенное изображение изделия. В галерее можно рассмотреть фотографии подробнее.' :
                'Показать выбранную фотографию как основное изображение в галерее этой страницы. Сохранённые фотографии изделия не изменяются.';
            const name = label(node);
            const actions = [
                [/^(Найти|Искать|Поиск)$/, 'Выполнить поиск по введённому запросу. Проверьте название или ключевые слова; результаты появятся в списке изделий.'],
                [/^(Отмена|Назад)$/, 'Вернуться к предыдущему разделу без отправки этой формы. Несохранённые изменения могут быть потеряны.'],
                [/^(Принять все|Разрешить все)/, 'Разрешить все категории cookies, описанные в настройках. Состав согласия можно изменить через настройки cookies в подвале.'],
                [/^(Только необходимые|Отклонить необязательные)/, 'Оставить только необходимые cookies для работы сайта. Дополнительные категории не будут включены.'],
                [/Показать изделия/, 'Применить выбранную категорию, поисковый запрос и диапазон цены. Список изделий обновится с учётом этих условий.'],
                [/Показать ещё/, 'Загрузить следующую порцию изделий, сохранив текущие фильтры и сортировку. Уже показанные карточки останутся на странице.'],
                [/Сбросить фильтры/, 'Снять условия поиска и фильтры каталога и снова показать все доступные изделия.'],
                [/Уточнить стоимость/, 'Открыть форму вопроса о стоимости этого изделия. Укажите контактные данные и детали, которые нужно учесть при расчёте.'],
                [/Заказать изготовление/, 'Открыть форму обращения по этому изделию. Оставьте контакты и пожелания к размерам, материалам или комплектации.'],
                [/Отправить отзыв/, 'Отправить заполненный отзыв об изделии. Проверьте оценку, текст и контактное имя перед отправкой.'],
                [/Отправить заявку/, 'Отправить заполненную заявку мастерской. Перед отправкой проверьте имя, телефон и описание задачи; обязательные поля будут проверены.'],
                [/^(Сохранить|Применить изменения)/, 'Сохранить изменения в текущей форме. Перед выполнением проверьте заполненные поля и выбранные параметры.'],
                [/^Удалить/, 'Запустить удаление выбранного элемента. Перед выполнением проверьте, что выбран нужный объект.'],
                [/^Очистить/, 'Очистить список или выбор, указанный на этой кнопке. Проверьте название действия перед выполнением.'],
                [/^(Предыдущая страница|Следующая страница)/, 'Перейти к соседней странице списка. Ссылки пагинации сохраняют условия, указанные в адресе перехода.'],
                [/Повторить/, 'Повторить последнюю неудачную загрузку, сохранив выбранные условия.'],
                [/Забыли пароль/, 'Перейти к восстановлению доступа. Потребуется адрес электронной почты, связанный с вашей учётной записью.'],
                [/^(Войти|Вход)/, node.matches('a[href]') ? 'Открыть форму входа в личный кабинет. Введите имя пользователя и пароль своей учётной записи.' : 'Отправить имя пользователя и пароль для входа в личный кабинет. Если данные неверны, форма покажет ошибку.'],
                [/Зарегистрироваться/, 'Перейти к созданию учётной записи. Заполните регистрационную форму и проверьте обязательные поля.'],
                [/Выйти/, 'Завершить текущий сеанс входа. Для доступа к личному кабинету потребуется войти снова.'],
                [/Настройки cookies/, 'Открыть настройки использования cookies и посмотреть доступные варианты согласия.'],
                [/^(Предыдущ|Следующ).*(фото|изображен)/i, 'Переключить фотографию в галерее изделия. Остальные данные страницы сохранятся.']
            ];
            for (const [pattern, text] of actions) if (pattern.test(name)) return text;
            if (node.matches('summary')) return (node.parentElement.open ? 'Свернуть' : 'Раскрыть') + ' блок «' + name + '». Это действие не отправляет форму и не изменяет данные.';
            if (node.matches('a[href]')) {
                let url;
                try { url = new URL(node.getAttribute('href'), location.href); } catch (_) { return 'Открыть ссылку «' + name + '».'; }
                if (node.hasAttribute('download')) return 'Скачать файл по этой ссылке. Браузер сохранит его или предложит выбрать место сохранения.';
                if (url.protocol === 'tel:') return 'Открыть приложение для звонка по указанному номеру. Соединение начнётся после подтверждения в приложении.';
                if (url.protocol === 'mailto:') return 'Открыть почтовое приложение для письма по указанному адресу. Письмо не отправляется автоматически.';
                if (url.origin !== location.origin) return 'Открыть внешний ресурс «' + name + '»' + (node.target === '_blank' ? ' в новой вкладке' : '') + '. Вы перейдёте на другой сайт или в соответствующее приложение.';
                const pages = [
                    ['/catalog/comparison/', 'Открыть таблицу выбранных изделий, чтобы сопоставить их характеристики и цены. Изделие добавляется кнопкой «Добавить к сравнению».'],
                    ['/wishlist/', 'Открыть изделия, которые вы сохранили в избранном, и перейти к их подробному описанию.'],
                    ['/account/dashboard/', 'Открыть личный кабинет: сохранённые изделия, ваши обращения и доступные настройки учётной записи.'],
                    ['/account/profile/edit/', 'Открыть редактирование данных профиля. Изменения применяются после сохранения формы.'],
                    ['/account/appointments/', 'Открыть историю ваших обращений и доступные сведения об их состоянии.'],
                    ['/account/favorites/', 'Открыть сохранённые изделия из избранного.'],
                    ['/catalog/recently-viewed/', 'Открыть список недавно просмотренных изделий, чтобы вернуться к заинтересовавшим вариантам.'],
                    ['/services/', 'Посмотреть направления мебельных и столярных работ, состав услуг и варианты индивидуального заказа.'],
                    ['/materials/', 'Узнать о материалах и фурнитуре, которые можно обсудить при подготовке вашего проекта.'],
                    ['/contacts/', 'Открыть опубликованные контакты мастерской и доступные способы связи.'],
                    ['/reviews/', 'Посмотреть опубликованные отзывы клиентов и связанные с ними изделия.'],
                    ['/about/', 'Узнать о подходе мастерской к проектированию, изготовлению и сборке мебели.'],
                    ['/privacy/', 'Прочитать информацию об обработке и защите персональных данных.'],
                    ['/consent/', 'Прочитать условия согласия на обработку персональных данных перед отправкой обращения.'],
                    ['/terms/', 'Прочитать опубликованные условия взаимодействия с мастерской.']
                ];
                for (const [path, text] of pages) if (url.pathname === path) return text;
                if (url.hash) {
                    const sections = {
                        '#callback':'Перейти к форме обращения. Опишите будущую мебель и оставьте контакты для обсуждения проекта.',
                        '#portfolio':'Перейти к подборке изделий на главной. Откройте карточку, чтобы рассмотреть фотографии и характеристики.',
                        '#categories':'Перейти к направлениям мебели и выбрать подходящую категорию каталога.',
                        '#advantages':'Перейти к разделу о подходе мастерской и преимуществах индивидуального изготовления.',
                        '#faq':'Перейти к частым вопросам. Нажмите на вопрос, чтобы раскрыть ответ.',
                        '#fd-description':'Перейти к описанию изделия на этой странице. Прочитайте особенности и обсудите индивидуальные изменения с мастерской.',
                        '#fd-specs':'Перейти к опубликованным характеристикам изделия. Отсутствующие параметры можно уточнить у мастерской.',
                        '#fd-reviews':'Перейти к отзывам об этом изделии на текущей странице.'
                    };
                    if (sections[url.hash]) return sections[url.hash];
                    return 'Перейти к разделу «' + name + '» на странице, чтобы прочитать подробности.';
                }
                if (url.pathname === '/catalog/') return url.search ?
                    'Открыть каталог с условиями, указанными в этой ссылке. Для изменения выбора используйте фильтры и сортировку.' :
                    'Открыть каталог мебели. Доступны поиск, выбор категории, фильтр цены и сортировка изделий.';
                if (/^\/catalog\/[^/]+\/$/.test(url.pathname) && !url.pathname.includes('/manage/')) return 'Открыть карточку «' + name.replace(/^Подробнее:\s*/, '') + '»: фотографии, описание, характеристики и обращение в мастерскую.';
                if (url.searchParams.has('page')) return 'Перейти на страницу ' + url.searchParams.get('page').replace(/[^0-9]/g, '').slice(0, 6) + ' этого списка. Остальные условия берутся из адреса ссылки.';
                if (url.pathname === '/') return 'Перейти на главную страницу мастерской: направления мебели, примеры изделий, материалы и форма обращения.';
                return 'Открыть «' + name + '»' + (node.target === '_blank' ? ' в новой вкладке' : '') + '.';
            }
            const title = active === node && originalTitle !== null ? originalTitle : node.getAttribute('title');
            if (title && compact(title) !== name) return title;
            return 'Выполнить действие «' + (name || 'кнопка') + '» в текущем разделе.';
        }
        function position() {
            if (!active || !active.isConnected) { hide(); return; }
            const viewportWidth = document.documentElement?.clientWidth || window.innerWidth;
            hint.style.maxWidth = Math.min(360, viewportWidth - 24) + 'px';
            const box = active.getBoundingClientRect();
            const rect = hint.getBoundingClientRect();
            const left = Math.max(12, Math.min(box.left, viewportWidth - rect.width - 12));
            let top = box.bottom + 10;
            if (top + rect.height > window.innerHeight - 12) top = Math.max(12, box.top - rect.height - 10);
            hint.style.left = left + 'px'; hint.style.top = top + 'px';
        }
        function hide() {
            clearTimeout(timer); clearTimeout(leaveTimer); timer = null; watcher.disconnect();
            if (active) {
                const ids = (active.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== hint.id);
                if (ids.length) active.setAttribute('aria-describedby', ids.join(' ')); else active.removeAttribute('aria-describedby');
                if (originalTitle !== null) active.setAttribute('title', originalTitle);
            }
            active = null; originalTitle = null; origin = null; hint.hidden = true;
        }
        function show(node, source) {
            clearTimeout(leaveTimer);
            if (active === node && !hint.hidden) return;
            hide(); active = node; origin = source;
            const reveal = function () {
                if (active !== node || !node.isConnected) return;
                originalTitle = node.getAttribute('title');
                if (originalTitle !== null) node.removeAttribute('title');
                hint.textContent = explain(node); hint.hidden = false;
                const ids = (node.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
                if (!ids.includes(hint.id)) ids.push(hint.id);
                node.setAttribute('aria-describedby', ids.join(' '));
                position();
                if (node.matches('summary')) watcher.observe(node.parentElement, {attributes:true, attributeFilter:['open']});
                watcher.observe(node, {attributes:true, attributeFilter:['class','aria-pressed','aria-expanded','aria-label'], childList:true, subtree:true, characterData:true});
            };
            if (source === 'focus') reveal(); else timer = setTimeout(reveal, 350);
        }
        function control(target) {
            const node = target.closest && target.closest('a[href],button,summary,input[type="submit"],input[type="button"]');
            return node && !node.disabled && !node.closest('[hidden],[aria-hidden="true"]') ? node : null;
        }
        document.addEventListener('pointerover', function (event) {
            if (event.pointerType === 'touch') return;
            touchInput = false;
            if (hint.contains(event.target)) { clearTimeout(leaveTimer); return; }
            const node = control(event.target); if (node) show(node, 'pointer');
        });
        document.addEventListener('pointerout', function (event) {
            if (origin === 'pointer' && active && !active.contains(event.relatedTarget) && !hint.contains(event.relatedTarget)) leaveTimer = setTimeout(hide, 180);
        });
        document.addEventListener('focusin', function (event) { const node = control(event.target); if (node && !touchInput) show(node, 'focus'); });
        document.addEventListener('focusout', function (event) { if (active && !active.contains(event.relatedTarget)) hide(); });
        document.addEventListener('pointerdown', function (event) { touchInput = event.pointerType === 'touch'; if (touchInput) hide(); });
        document.addEventListener('keydown', function (event) { if (event.key === 'Tab') touchInput = false; if (event.key === 'Escape') hide(); });
        document.addEventListener('scroll', function () {
            if (origin === 'focus' && active) position(); else hide();
        }, true);
        window.addEventListener('resize', hide);
        // Старый AJAX-узел не должен оставлять пояснение над новой выдачей.
        document.addEventListener('catalog:updated', hide);
    });
})();
