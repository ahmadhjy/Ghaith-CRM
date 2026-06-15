(function () {
    function renumberPassengers(list) {
        list.querySelectorAll('.req-passengers__row').forEach(function (row, i) {
            var badge = row.querySelector('.req-passengers__index');
            if (badge) badge.textContent = String(i + 1);
        });
    }

    function addPassengerRow(list) {
        var row = document.createElement('div');
        row.className = 'req-passengers__row';
        row.innerHTML =
            '<span class="req-passengers__index" aria-hidden="true"></span>' +
            '<input type="text" name="passenger_names" class="req-input" placeholder="Passenger full name">' +
            '<button type="button" class="req-btn req-btn--ghost req-btn--sm js-remove-passenger" title="Remove">' +
            '<i class="fas fa-times"></i></button>';
        list.appendChild(row);
        renumberPassengers(list);
        row.querySelector('input').focus();
    }

    document.addEventListener('click', function (e) {
        var addBtn = e.target.closest('.js-add-passenger');
        if (addBtn) {
            var list = addBtn.closest('.req-passengers').querySelector('.js-passengers-list');
            addPassengerRow(list);
            return;
        }
        var removeBtn = e.target.closest('.js-remove-passenger');
        if (removeBtn) {
            var row = removeBtn.closest('.req-passengers__row');
            var list = removeBtn.closest('.js-passengers-list');
            if (row && list) {
                if (list.querySelectorAll('.req-passengers__row').length > 1) {
                    row.remove();
                    renumberPassengers(list);
                } else {
                    row.querySelector('input').value = '';
                }
            }
        }
    });

    document.querySelectorAll('.js-passengers-list').forEach(renumberPassengers);
})();
