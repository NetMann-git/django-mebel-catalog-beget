(function () {
    'use strict';
    function update(fields) {
        var direction = fields.querySelector('[name="direction"]');
        var row = fields.querySelector('[data-estimate-layout]');
        if (!direction || !row) return;
        var visible = direction.value === 'kuhni';
        row.hidden = !visible;
        row.querySelectorAll('select,input').forEach(function (input) { input.disabled = !visible; });
    }
    function scan(root) {
        if (root.matches && root.matches('.estimate-fields')) update(root);
        if (root.querySelectorAll) root.querySelectorAll('.estimate-fields').forEach(update);
    }
    document.addEventListener('change', function (event) {
        if (event.target.matches('[name="direction"]')) {
            var fields = event.target.closest('.estimate-fields');
            if (fields) update(fields);
        }
    });
    document.addEventListener('DOMContentLoaded', function () {
        scan(document);
        new MutationObserver(function (changes) {
            changes.forEach(function (change) { change.addedNodes.forEach(scan); });
        }).observe(document.body, {childList:true, subtree:true});
    });
})();
