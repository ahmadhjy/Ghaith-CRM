(function () {
    function addPassengerRow(list) {
        var row = document.createElement('div');
        row.className = 'req-passengers__row';
        row.innerHTML =
            '<input type="text" name="passenger_names" class="req-input" placeholder="Passenger name">' +
            '<button type="button" class="req-btn req-btn--ghost req-btn--sm js-remove-passenger" title="Remove">' +
            '<i class="fas fa-times"></i></button>';
        list.appendChild(row);
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
            if (row) row.remove();
        }
    });
})();
