/* TwoComms Finance — форма рахунку-фактури: позиції, live-підрахунок, збереження. */
(function () {
  'use strict';
  var form = document.getElementById('fin-invoice-form');
  if (!form) return;

  function csrf() { var m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ''; }
  function num(v) { var n = parseFloat(String(v).replace(',', '.')); return isNaN(n) ? 0 : n; }

  var itemsBody = document.getElementById('inv-items');

  function rowTemplate() {
    var tr = document.createElement('tr');
    tr.className = 'inv-item';
    tr.innerHTML =
      '<td><input class="fin-input inv-item-name"></td>' +
      '<td><input type="number" step="0.001" class="fin-input fin-input--sm inv-item-qty" value="1"></td>' +
      '<td><input type="number" step="0.01" class="fin-input fin-input--sm inv-item-price" value="0"></td>' +
      '<td class="inv-item-amount">0</td>' +
      '<td><button type="button" class="fin-icon-btn fin-icon-btn--sm inv-item-del">×</button></td>';
    return tr;
  }

  function recalc() {
    var subtotal = 0;
    itemsBody.querySelectorAll('.inv-item').forEach(function (row) {
      var q = num(row.querySelector('.inv-item-qty').value);
      var p = num(row.querySelector('.inv-item-price').value);
      var amt = q * p;
      row.querySelector('.inv-item-amount').textContent = amt.toFixed(2);
      subtotal += amt;
    });
    var discount = num(document.getElementById('inv-discount').value);
    var delivery = num(document.getElementById('inv-delivery').value);
    var vatOn = document.getElementById('inv-vat').checked;
    var rate = num(document.getElementById('inv-vat-rate').value);
    var tax = vatOn ? (subtotal * rate / 100) : 0;
    var total = subtotal - discount + delivery + tax;
    document.getElementById('inv-subtotal').textContent = subtotal.toFixed(2);
    document.getElementById('inv-tax').textContent = tax.toFixed(2);
    document.getElementById('inv-total').textContent = total.toFixed(2);
    document.getElementById('inv-tax-row').hidden = !vatOn;
    document.getElementById('inv-vat-rate-wrap').hidden = !vatOn;
  }

  form.addEventListener('input', recalc);
  document.getElementById('inv-vat').addEventListener('change', recalc);
  document.getElementById('inv-add-item').addEventListener('click', function () {
    itemsBody.appendChild(rowTemplate());
    recalc();
  });
  itemsBody.addEventListener('click', function (e) {
    if (e.target.closest('.inv-item-del')) { e.target.closest('.inv-item').remove(); recalc(); }
  });

  function collectItems() {
    return Array.prototype.slice.call(itemsBody.querySelectorAll('.inv-item')).map(function (row) {
      return {
        name: row.querySelector('.inv-item-name').value,
        quantity: row.querySelector('.inv-item-qty').value,
        unit_price: row.querySelector('.inv-item-price').value,
      };
    }).filter(function (i) { return i.name.trim(); });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var alert = document.getElementById('fin-inv-alert');
    var payload = {
      number: document.getElementById('inv-number').value,
      currency: document.getElementById('inv-currency').value,
      issue_date: document.getElementById('inv-issue').value,
      due_date: document.getElementById('inv-due').value,
      status: document.getElementById('inv-status').value,
      vat_enabled: document.getElementById('inv-vat').checked,
      vat_rate: document.getElementById('inv-vat-rate').value,
      discount_amount: document.getElementById('inv-discount').value,
      delivery_amount: document.getElementById('inv-delivery').value,
      notes: document.getElementById('inv-notes').value,
      counterparty: document.getElementById('inv-counterparty').value,
      supplier_name: document.getElementById('inv-sup-name').value,
      supplier_edrpou: document.getElementById('inv-sup-edrpou').value,
      supplier_iban: document.getElementById('inv-sup-iban').value,
      supplier_address: document.getElementById('inv-sup-address').value,
      payer_name: document.getElementById('inv-pay-name').value,
      payer_edrpou: document.getElementById('inv-pay-edrpou').value,
      payer_iban: document.getElementById('inv-pay-iban').value,
      payer_address: document.getElementById('inv-pay-address').value,
      items: collectItems(),
    };
    fetch(form.dataset.saveUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(payload),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) { window.location.href = '/invoices/'; }
      else { alert.textContent = d.error || 'Помилка збереження'; alert.hidden = false; }
    });
  });

  recalc();
})();
