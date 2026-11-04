/* шаг 02: доступное мобильное меню; FAQ работает без JavaScript. */
(function () {
  'use strict';
  // шаг 54: телефон и переносы строк могут менять высоту шапки.
  var header = document.querySelector('.furniture-home .fm-header');
  if (header) {
    var updateHeaderHeight = function () {
      document.body.style.setProperty('--fm-header-height', Math.ceil(header.getBoundingClientRect().height) + 'px');
    };
    updateHeaderHeight();
    if ('ResizeObserver' in window) {
      new ResizeObserver(updateHeaderHeight).observe(header);
    } else {
      window.addEventListener('resize', updateHeaderHeight);
    }
  }
  var button = document.querySelector('.fm-menu-toggle');
  var navigation = document.getElementById('fm-navigation');
  if (!button || !navigation) return;
  function closeMenu() {
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Открыть меню');
    navigation.classList.remove('is-open');
  }
  button.addEventListener('click', function () {
    var open = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
    navigation.classList.toggle('is-open', open);
  });
  navigation.addEventListener('click', function (event) { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') { closeMenu(); button.focus(); }
  });
  window.matchMedia('(min-width: 1081px)').addEventListener('change', closeMenu);
})();
