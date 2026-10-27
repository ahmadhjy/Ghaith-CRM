// Run with: node tasks/tests_service_order.js
// Exercise the template's actual reorder functions without browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const template = fs.readFileSync(path.join(__dirname, 'templates/edit_leadtask.html'), 'utf8');
const start = template.indexOf('function serviceRows()');
const end = template.indexOf('var initialStatus', start);
assert.ok(start > 0 && end > start);
const rows = [];
const parent = {
    insertBefore(row, adjacent) {
        rows.splice(rows.indexOf(row), 1);
        rows.splice(rows.indexOf(adjacent), 0, row);
    },
};
function makeRow(id) {
    const controls = {
        '.service-sort-order': { value: '' },
        '.service-move-up': { disabled: false },
        '.service-move-down': { disabled: false },
        '.attachment-move-up': { disabled: false },
        '.attachment-move-down': { disabled: false },
    };
    const row = {
        id, parentNode: parent,
        querySelector: selector => controls[selector],
        remove: () => rows.splice(rows.indexOf(row), 1),
    };
    return row;
}
let dirty = false;
let recalculated = false;
rows.push(makeRow('existing-a'), makeRow('new'), makeRow('existing-b'));
const context = {
    document: { querySelectorAll: () => rows },
    markInvoiceDirty: () => { dirty = true; },
    recalcProfit: () => { recalculated = true; },
};
vm.createContext(context);
vm.runInContext(template.slice(start, end), context);
function button(row) { return { closest: () => row }; }
function verify(expected) {
    assert.deepEqual(rows.map(row => row.id), expected);
    rows.forEach((row, index) => {
        assert.equal(row.querySelector('.service-sort-order').value, index + 1);
        assert.equal(row.querySelector('.service-move-up').disabled, index === 0);
        assert.equal(row.querySelector('.service-move-down').disabled, index === rows.length - 1);
    });
}
verify(['existing-a', 'new', 'existing-b']);
const newRow = rows[1];
context.moveServiceRow(button(newRow), -1);
verify(['new', 'existing-a', 'existing-b']);
assert.equal(dirty, true);
context.moveServiceRow(button(newRow), -1); // Upper boundary: no change.
verify(['new', 'existing-a', 'existing-b']);
context.moveServiceRow(button(newRow), 1);
verify(['existing-a', 'new', 'existing-b']);
context.moveServiceRow(button(rows[2]), 1); // Lower boundary: no change.
verify(['existing-a', 'new', 'existing-b']);
context.removeNewServiceRow(button(newRow));
verify(['existing-a', 'existing-b']);
assert.equal(recalculated, true);
context.removeNewServiceRow(button(rows[1]));
verify(['existing-a']);
context.removeNewServiceRow(button(rows[0]));
verify([]);
console.log('Service row reordering: all checks passed.');

// Check the actual attachment handlers too; hidden form inputs move with rows.
rows.push(makeRow('file-a'), makeRow('file-b'), makeRow('file-c'));
const attachmentStart = template.indexOf('function attachmentRows()');
const attachmentEnd = template.indexOf('function addRow()', attachmentStart);
assert.ok(attachmentStart > 0 && attachmentEnd > attachmentStart);
dirty = false;
vm.runInContext(template.slice(attachmentStart, attachmentEnd), context);
assert.equal(rows[0].querySelector('.attachment-move-up').disabled, true);
assert.equal(rows[2].querySelector('.attachment-move-down').disabled, true);
const attachment = rows[1];
context.moveAttachmentRow(button(attachment), -1);
assert.deepEqual(rows.map(row => row.id), ['file-b', 'file-a', 'file-c']);
assert.equal(dirty, true);
assert.equal(attachment.querySelector('.attachment-move-up').disabled, true);
context.moveAttachmentRow(button(attachment), -1);
assert.deepEqual(rows.map(row => row.id), ['file-b', 'file-a', 'file-c']);
context.moveAttachmentRow(button(attachment), 1);
assert.deepEqual(rows.map(row => row.id), ['file-a', 'file-b', 'file-c']);
context.moveAttachmentRow(button(rows[2]), 1);
assert.deepEqual(rows.map(row => row.id), ['file-a', 'file-b', 'file-c']);

const sentValue = { value: '' };
const newCheckbox = {
    checked: true,
    closest: () => ({ querySelector: () => sentValue }),
};
context.syncNewServiceSendToClient(newCheckbox);
assert.equal(sentValue.value, 'on');
newCheckbox.checked = false;
context.syncNewServiceSendToClient(newCheckbox);
assert.equal(sentValue.value, '');
console.log('Attachment row ordering and new-service flags: all checks passed.');
