function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function isoToDateInput(iso) {
  if (!iso) return '';
  try {
    return iso.slice(0, 10);
  } catch (e) {
    return '';
  }
}

function isoToDateTimeLocal(iso) {
  if (!iso) return '';
  try {
    // expects "YYYY-MM-DDTHH:MM:SS..." -> "YYYY-MM-DDTHH:MM"
    return iso.slice(0, 16);
  } catch (e) {
    return '';
  }
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = String(s ?? '');
  return div.innerHTML;
}

function createUID(prefix) {
  const rand = Math.random().toString(16).slice(2);
  return `${prefix}_${Date.now()}_${rand}`;
}

document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  const shopsDataEl = document.getElementById('shops-data');
  const shops = shopsDataEl ? JSON.parse(shopsDataEl.textContent || '[]') : [];

  const testProductsDataEl = document.getElementById('test-products-data');
  const testProducts = testProductsDataEl ? JSON.parse(testProductsDataEl.textContent || '[]') : [];

  const shopModal = document.getElementById('shop-modal');
  const shopForm = document.getElementById('shop-form');
  const shopModalTitle = document.getElementById('shop-modal-title');

  const invoicesModal = document.getElementById('shop-invoices-modal');
  const invoicesTitle = document.getElementById('shop-invoices-title');
  const invoicesBody = document.getElementById('shop-invoices-body');

  const manageModal = document.getElementById('shop-manage-modal');
  const manageTitle = document.getElementById('shop-manage-title');
  const manageCommList = document.getElementById('shop-comm-list');
  const manageInventory = document.getElementById('shop-inventory');

  const phonesWrap = document.getElementById('phones-wrap');
  const shipmentsWrap = document.getElementById('shipments-wrap');
  const addPhoneBtn = document.getElementById('add-phone-btn');
  const addShipmentBtn = document.getElementById('add-shipment-btn');

  const testFields = document.getElementById('test-fields');
  const testPackageMode = document.getElementById('test_package_mode');
  const testPackageValue = document.getElementById('test_package_value');
  const testPackageJson = document.getElementById('test_package_json');

  let currentShopId = null;
  let invoicesCache = null;

  function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add('show');
    body.classList.add('modal-open');
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove('show');
    body.classList.remove('modal-open');
  }

  document.querySelectorAll('.modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal(overlay);
    });
  });
  document.querySelectorAll('.modal-close').forEach((btn) => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      closeModal(modal);
    });
  });

  function applyChannelToggle(toggleInput) {
    const targetId = toggleInput.dataset.toggle;
    if (!targetId) return;
    const field = document.getElementById(targetId);
    if (!field) return;
    field.style.display = toggleInput.checked ? '' : 'none';
    if (!toggleInput.checked) field.value = '';
  }

  document.querySelectorAll('input[type="checkbox"][data-toggle]').forEach((cb) => {
    cb.addEventListener('change', () => applyChannelToggle(cb));
  });

  function updateTestFieldsVisibility() {
    const selected = shopForm.querySelector('input[name="shop_type"]:checked');
    const isTest = selected && selected.value === 'test';
    testFields.style.display = isTest ? '' : 'none';
    if (!isTest) {
      document.getElementById('test_product_id').value = '';
      document.getElementById('test_connected_at').value = '';
      testPackageMode.value = 'rostovka';
      testPackageValue.value = '';
      testPackageJson.value = '';
    }
  }

  shopForm.querySelectorAll('input[name="shop_type"]').forEach((r) => {
    r.addEventListener('change', updateTestFieldsVisibility);
  });

  function syncTestPackageJson() {
    const mode = testPackageMode.value || 'rostovka';
    const value = (testPackageValue.value || '').trim();
    const payload = { mode, value };
    testPackageJson.value = JSON.stringify(payload);
  }
  testPackageMode.addEventListener('change', syncTestPackageJson);
  testPackageValue.addEventListener('input', syncTestPackageJson);

  async function ensureInvoicesLoaded() {
    if (Array.isArray(invoicesCache)) return invoicesCache;
    const res = await fetch('/invoices/api/list/');
    const data = await res.json().catch(() => ({}));
    if (!data.ok) throw new Error(data.error || 'Не вдалося завантажити список накладних');
    invoicesCache = data.invoices || [];
    return invoicesCache;
  }

  function renderPhoneRow(p) {
    const rowId = createUID('phone');
    const role = (p && p.role) ? p.role : 'owner';
    const roleOther = (p && p.role_other) ? p.role_other : '';
    const phone = (p && p.phone) ? p.phone : '';
    const isPrimary = !!(p && p.is_primary);

    const el = document.createElement('div');
    el.className = 'repeater-row phone-row';
    el.dataset.rowId = rowId;
    el.innerHTML = `
      <div class="row-grid">
        <div class="field">
          <label>Роль</label>
          <select class="phone-role">
            <option value="owner">Власник</option>
            <option value="manager">Менеджер</option>
            <option value="admin">Адміністратор</option>
            <option value="other">Інший</option>
          </select>
        </div>
        <div class="field phone-role-other-field" style="display:none;">
          <label>Хто це</label>
          <input type="text" class="phone-role-other" placeholder="Напр.: бухгалтер" />
        </div>
        <div class="field">
          <label>Телефон</label>
          <input type="text" class="phone-number" placeholder="+380..." />
        </div>
        <div class="field">
          <label>Основний</label>
          <label class="checkline">
            <input type="radio" name="primary_phone" class="phone-primary" />
            <span>Так</span>
          </label>
        </div>
        <div class="row-actions">
          <button type="button" class="btn-ghost small danger phone-remove">Видалити</button>
        </div>
      </div>
    `;

    const roleSel = el.querySelector('.phone-role');
    const roleOtherField = el.querySelector('.phone-role-other-field');
    const roleOtherInput = el.querySelector('.phone-role-other');
    const phoneInput = el.querySelector('.phone-number');
    const primaryRadio = el.querySelector('.phone-primary');

    roleSel.value = role;
    roleOtherInput.value = roleOther;
    phoneInput.value = phone;
    primaryRadio.checked = isPrimary;

    const toggleOther = () => {
      const isOther = roleSel.value === 'other';
      roleOtherField.style.display = isOther ? '' : 'none';
      if (!isOther) roleOtherInput.value = '';
    };
    roleSel.addEventListener('change', toggleOther);
    toggleOther();

    el.querySelector('.phone-remove').addEventListener('click', () => {
      el.remove();
      ensureAtLeastOnePhone();
      ensureOnePrimaryPhone();
    });

    primaryRadio.addEventListener('change', ensureOnePrimaryPhone);

    return el;
  }

  function ensureAtLeastOnePhone() {
    if (!phonesWrap.querySelector('.phone-row')) {
      phonesWrap.appendChild(renderPhoneRow({ role: 'owner', phone: '' }));
      ensureOnePrimaryPhone();
    }
  }

  function ensureOnePrimaryPhone() {
    const radios = Array.from(phonesWrap.querySelectorAll('.phone-primary'));
    if (!radios.length) return;
    if (!radios.some(r => r.checked)) radios[0].checked = true;
  }

  function shipmentInvoiceSystemOptionsHtml() {
    if (!Array.isArray(invoicesCache)) return '<option value="">(завантаження...)</option>';
    const opts = ['<option value="">—</option>'];
    invoicesCache.forEach((inv) => {
      const label = `#${inv.invoice_number} • ${inv.company_name} • ${inv.total_amount} грн • ${inv.created_at}`;
      opts.push(`<option value="${inv.id}">${escapeHtml(label)}</option>`);
    });
    return opts.join('');
  }

  function renderShipmentRow(s) {
    const rowId = createUID('ship');
    const shipmentId = (s && s.id) ? String(s.id) : '';
    const ttn = (s && s.ttn_number) ? s.ttn_number : '';
    const shippedAt = (s && s.shipped_at) ? s.shipped_at : '';
    const isTest = !!(s && s.is_test_batch);
    const invoiceKind = (s && s.invoice_kind) ? s.invoice_kind : 'none';
    const wholesaleInvoiceId = (s && s.wholesale_invoice_id) ? String(s.wholesale_invoice_id) : '';
    const invoiceTitle = (s && s.invoice_title) ? s.invoice_title : '';
    const invoiceDownloadUrl = (s && s.invoice_download_url) ? s.invoice_download_url : '';
    const fileField = `shipment_file_${rowId}`;

    const el = document.createElement('div');
    el.className = 'repeater-row shipment-row';
    el.dataset.rowId = rowId;
    if (shipmentId) el.dataset.shipmentId = shipmentId;
    el.dataset.fileField = fileField;
    el.innerHTML = `
      <div class="field-grid">
        <div class="field">
          <label>ТТН</label>
          <input type="text" class="shipment-ttn" placeholder="2040..." />
        </div>
        <div class="field">
          <label>Дата відправки</label>
          <input type="date" class="shipment-date" />
        </div>
        <div class="field">
          <label>Накладна</label>
          <select class="shipment-invoice-kind">
            <option value="none">—</option>
            <option value="system">Вибрати з накладних</option>
            <option value="upload">Завантажити Excel</option>
          </select>
        </div>
        <div class="field shipment-invoice-system" style="display:none;">
          <label>Накладна (система)</label>
          <select class="shipment-invoice-select"></select>
        </div>
        <div class="field shipment-invoice-upload" style="display:none;">
          <label>Excel</label>
          <input type="file" class="shipment-invoice-file" name="${fileField}" accept=".xlsx,.xlsm,.xls" />
        </div>
        <div class="field checkbox-field">
          <label class="checkline">
            <input type="checkbox" class="shipment-is-test" />
            <span>Тестова партія</span>
          </label>
        </div>
      </div>
      <div class="row-actions">
        <div class="shipment-current" style="flex:1; color: var(--text-secondary); font-size: 0.9rem;"></div>
        <button type="button" class="btn-ghost small danger shipment-remove">Видалити</button>
      </div>
    `;

    el.querySelector('.shipment-ttn').value = ttn;
    el.querySelector('.shipment-date').value = shippedAt ? shippedAt.slice(0, 10) : '';
    el.querySelector('.shipment-is-test').checked = isTest;

    const kindSel = el.querySelector('.shipment-invoice-kind');
    const sysWrap = el.querySelector('.shipment-invoice-system');
    const upWrap = el.querySelector('.shipment-invoice-upload');
    const invSel = el.querySelector('.shipment-invoice-select');
    const currentInfo = el.querySelector('.shipment-current');

    invSel.innerHTML = shipmentInvoiceSystemOptionsHtml();
    if (wholesaleInvoiceId) invSel.value = wholesaleInvoiceId;

    const refreshKind = () => {
      const kind = kindSel.value;
      sysWrap.style.display = kind === 'system' ? '' : 'none';
      upWrap.style.display = kind === 'upload' ? '' : 'none';
      if (kind !== 'system') invSel.value = '';
      if (kind !== 'upload') el.querySelector('.shipment-invoice-file').value = '';
      currentInfo.innerHTML = '';
      if (invoiceTitle) {
        const badge = `<span class="shop-muted">Поточне:</span> ${escapeHtml(invoiceTitle)}`;
        const dl = invoiceDownloadUrl ? ` • <a href="${escapeHtml(invoiceDownloadUrl)}" target="_blank" rel="noopener">скачати</a>` : '';
        currentInfo.innerHTML = badge + dl;
      }
    };

    kindSel.value = invoiceKind;
    kindSel.addEventListener('change', refreshKind);
    refreshKind();

    el.querySelector('.shipment-remove').addEventListener('click', () => {
      el.remove();
      ensureAtLeastOneShipment();
    });

    return el;
  }

  function ensureAtLeastOneShipment() {
    if (!shipmentsWrap.querySelector('.shipment-row')) {
      shipmentsWrap.appendChild(renderShipmentRow({ invoice_kind: 'none' }));
    }
  }

  addPhoneBtn.addEventListener('click', () => {
    phonesWrap.appendChild(renderPhoneRow({ role: 'other', phone: '' }));
    ensureOnePrimaryPhone();
  });

  addShipmentBtn.addEventListener('click', async () => {
    try {
      await ensureInvoicesLoaded();
    } catch (e) {
      // ignore; user may still add upload invoice
    }
    shipmentsWrap.appendChild(renderShipmentRow({ invoice_kind: 'none' }));
  });

  function resetShopForm() {
    shopForm.reset();
    document.getElementById('shop_id').value = '';
    phonesWrap.innerHTML = '';
    shipmentsWrap.innerHTML = '';
    document.getElementById('website_url').style.display = 'none';
    document.getElementById('instagram_url').style.display = 'none';
    document.getElementById('prom_url').style.display = 'none';
    document.getElementById('other_sales_channel').style.display = 'none';
    document.getElementById('ch_website').checked = false;
    document.getElementById('ch_instagram').checked = false;
    document.getElementById('ch_prom').checked = false;
    document.getElementById('ch_other').checked = false;
    testFields.style.display = 'none';
    testPackageMode.value = 'rostovka';
    testPackageValue.value = '';
    testPackageJson.value = '';
    ensureAtLeastOnePhone();
    ensureAtLeastOneShipment();
  }

  async function openCreateShop() {
    currentShopId = null;
    shopModalTitle.textContent = 'Додати магазин';
    resetShopForm();
    updateTestFieldsVisibility();
    try {
      await ensureInvoicesLoaded();
      // Update existing selects for shipment rows
      shipmentsWrap.querySelectorAll('.shipment-invoice-select').forEach((sel) => {
        sel.innerHTML = shipmentInvoiceSystemOptionsHtml();
      });
    } catch (e) {}
    openModal(shopModal);
  }

  async function openEditShop(shopId) {
    const shop = shops.find((x) => String(x.id) === String(shopId));
    if (!shop) return;
    currentShopId = shopId;
    shopModalTitle.textContent = 'Редагувати магазин';
    resetShopForm();

    document.getElementById('shop_id').value = shop.id;
    document.getElementById('shop_name').value = shop.name || '';
    document.getElementById('owner_full_name').value = shop.owner_full_name || '';
    document.getElementById('registration_place').value = shop.registration_place || '';
    document.getElementById('is_physical').checked = !!shop.is_physical;
    document.getElementById('city').value = shop.city || '';
    document.getElementById('address').value = shop.address || '';
    document.getElementById('notes').value = shop.notes || '';

    const setChannel = (cbId, inputId, value) => {
      const cb = document.getElementById(cbId);
      const input = document.getElementById(inputId);
      cb.checked = !!value;
      input.style.display = cb.checked ? '' : 'none';
      input.value = value || '';
    };
    setChannel('ch_website', 'website_url', shop.website_url);
    setChannel('ch_instagram', 'instagram_url', shop.instagram_url);
    setChannel('ch_prom', 'prom_url', shop.prom_url);
    setChannel('ch_other', 'other_sales_channel', shop.other_sales_channel);

    const typeRadio = shopForm.querySelector(`input[name="shop_type"][value="${shop.shop_type}"]`);
    if (typeRadio) typeRadio.checked = true;
    updateTestFieldsVisibility();
    if (shop.shop_type === 'test') {
      document.getElementById('test_product_id').value = shop.test_product_id || '';
      document.getElementById('test_connected_at').value = shop.test_connected_at ? shop.test_connected_at.slice(0, 10) : '';
      const tp = shop.test_package || {};
      testPackageMode.value = tp.mode || 'rostovka';
      testPackageValue.value = tp.value || '';
      syncTestPackageJson();
    }

    phonesWrap.innerHTML = '';
    (shop.phones || []).forEach((p) => phonesWrap.appendChild(renderPhoneRow(p)));
    ensureAtLeastOnePhone();
    ensureOnePrimaryPhone();

    try { await ensureInvoicesLoaded(); } catch (e) {}
    shipmentsWrap.innerHTML = '';
    (shop.shipments || []).forEach((s) => shipmentsWrap.appendChild(renderShipmentRow(s)));
    ensureAtLeastOneShipment();

    openModal(shopModal);
  }

  document.getElementById('shop-add-card').addEventListener('click', openCreateShop);

  document.getElementById('shops-grid').addEventListener('click', async (e) => {
    const card = e.target.closest('.shop-card[data-shop-id]');
    if (!card) return;
    const shopId = card.dataset.shopId;
    const actionBtn = e.target.closest('button[data-action]');
    if (!actionBtn) return;
    const action = actionBtn.dataset.action;

    if (action === 'edit') {
      await openEditShop(shopId);
    } else if (action === 'invoices') {
      await openInvoicesModal(shopId);
    } else if (action === 'manage') {
      await openManageModal(shopId);
    } else if (action === 'delete') {
      await deleteShop(shopId);
    }
  });

  function collectPhones() {
    const rows = Array.from(phonesWrap.querySelectorAll('.phone-row'));
    const primaryRow = rows.find((r) => r.querySelector('.phone-primary').checked) || rows[0];
    const data = [];
    rows.forEach((row, idx) => {
      const role = row.querySelector('.phone-role').value;
      const roleOther = row.querySelector('.phone-role-other')?.value || '';
      const phone = row.querySelector('.phone-number').value || '';
      if (!phone.trim()) return;
      data.push({
        role,
        role_other: role === 'other' ? roleOther.trim() : '',
        phone: phone.trim(),
        is_primary: row === primaryRow,
        sort_order: idx,
      });
    });
    return data;
  }

  function collectShipments() {
    const rows = Array.from(shipmentsWrap.querySelectorAll('.shipment-row'));
    const data = [];
    rows.forEach((row, idx) => {
      const ttn = row.querySelector('.shipment-ttn').value || '';
      const date = row.querySelector('.shipment-date').value || '';
      if (!ttn.trim() || !date.trim()) return;
      const kind = row.querySelector('.shipment-invoice-kind').value || 'none';
      const invSel = row.querySelector('.shipment-invoice-select');
      const fileInput = row.querySelector('.shipment-invoice-file');
      const isTest = row.querySelector('.shipment-is-test').checked;

      const payload = {
        id: row.dataset.shipmentId ? parseInt(row.dataset.shipmentId, 10) : undefined,
        ttn_number: ttn.trim(),
        shipped_at: date,
        is_test_batch: !!isTest,
        invoice_kind: kind,
      };

      if (kind === 'system') {
        payload.wholesale_invoice_id = invSel.value ? parseInt(invSel.value, 10) : null;
      } else if (kind === 'upload') {
        if (fileInput.files && fileInput.files[0]) {
          payload.file_field = row.dataset.fileField;
        } else {
          payload.file_field = '';
        }
      }

      // For test shops: make first shipment test batch if none selected
      data.push(payload);
    });

    if (data.length && shopForm.querySelector('input[name="shop_type"]:checked')?.value === 'test') {
      if (!data.some((x) => x.is_test_batch)) data[0].is_test_batch = true;
    }

    return data;
  }

  shopForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('shop-save-btn');
    saveBtn.disabled = true;
    try {
      syncTestPackageJson();
      const phones = collectPhones();
      const shipments = collectShipments();
      if (!phones.length) throw new Error('Додайте мінімум 1 номер телефону');
      if (!shipments.length) throw new Error('Додайте мінімум 1 ТТН');

      const isPhysical = document.getElementById('is_physical').checked;
      if (isPhysical) {
        const city = (document.getElementById('city').value || '').trim();
        const addr = (document.getElementById('address').value || '').trim();
        if (!city || !addr) throw new Error('Для фізичного магазину вкажіть місто та адресу');
      }

      const fd = new FormData(shopForm);
      fd.set('phones_json', JSON.stringify(phones));
      fd.set('shipments_json', JSON.stringify(shipments));

      // attach shipment files
      shipmentsWrap.querySelectorAll('.shipment-row').forEach((row) => {
        const kind = row.querySelector('.shipment-invoice-kind').value || 'none';
        if (kind !== 'upload') return;
        const fileInput = row.querySelector('.shipment-invoice-file');
        const fileField = row.dataset.fileField;
        if (fileInput && fileInput.files && fileInput.files[0] && fileField) {
          fd.append(fileField, fileInput.files[0]);
        }
      });

      const res = await fetch('/shops/api/save/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || 'Помилка збереження');
      window.location.reload();
    } catch (err) {
      alert(err.message || 'Помилка');
      saveBtn.disabled = false;
    }
  });

  async function fetchShopDetail(shopId) {
    const res = await fetch(`/shops/api/detail/${shopId}/`);
    const data = await res.json().catch(() => ({}));
    if (!data.ok) throw new Error(data.error || 'Не вдалося завантажити дані магазину');
    return data;
  }

  function renderShipmentSummaryCard(s) {
    const sum = s.invoice_summary || {};
    const items = Array.isArray(sum.items) ? sum.items : [];
    const totalAmount = s.invoice_total_amount || sum.total_amount || '';
    const download = s.invoice_download_url ? `<a class="btn-ghost small" href="${escapeHtml(s.invoice_download_url)}" target="_blank" rel="noopener">Скачати Excel</a>` : '';

    const lines = [];
    if (items.length) {
      items.slice(0, 10).forEach((it) => {
        const title = it.title || '';
        const size = it.size ? ` • ${it.size}` : '';
        const color = it.color ? ` • ${it.color}` : '';
        const qty = it.quantity != null ? ` × ${it.quantity}` : '';
        lines.push(`<div>• ${escapeHtml(title)}${escapeHtml(size)}${escapeHtml(color)}${escapeHtml(qty)}</div>`);
      });
      if (items.length > 10) lines.push(`<div class="shop-muted">…ще ${items.length - 10} позицій</div>`);
    } else {
      lines.push(`<div class="shop-muted">Немає сводки по позиціях</div>`);
    }

    return `
      <div class="shipment-card">
        <div class="shipment-head">
          <div>
            <div class="shipment-title">ТТН: ${escapeHtml(s.ttn_number || '')}</div>
            <div class="shipment-meta">${escapeHtml(s.shipped_at || '')}${totalAmount ? ` • Сума: ${escapeHtml(totalAmount)} грн` : ''}</div>
          </div>
          <div>${download}</div>
        </div>
        <div class="shipment-items">${lines.join('')}</div>
      </div>
    `;
  }

  async function openInvoicesModal(shopId) {
    currentShopId = shopId;
    invoicesTitle.textContent = 'Накладні магазину';
    invoicesBody.innerHTML = '<div class="shop-muted">Завантаження…</div>';
    openModal(invoicesModal);
    try {
      const detail = await fetchShopDetail(shopId);
      const shop = detail.shop || {};
      invoicesTitle.textContent = `Накладні: ${shop.name || ''}`;
      const shipments = detail.shipments || [];
      if (!shipments.length) {
        invoicesBody.innerHTML = '<div class="shop-muted">Немає ТТН/накладних</div>';
        return;
      }
      invoicesBody.innerHTML = shipments.map(renderShipmentSummaryCard).join('');
    } catch (err) {
      invoicesBody.innerHTML = `<div class="shop-muted">${escapeHtml(err.message || 'Помилка')}</div>`;
    }
  }

  function renderCommItem(c) {
    const when = c.contacted_at ? c.contacted_at.slice(0, 16).replace('T', ' ') : '';
    const person = c.contact_person ? `<span class="shop-muted">•</span> ${escapeHtml(c.contact_person)}` : '';
    const phone = c.phone ? `<span class="shop-muted">•</span> ${escapeHtml(c.phone)}` : '';
    const note = c.note ? `<div class="shop-meta">${escapeHtml(c.note)}</div>` : '';
    return `
      <div class="shop-comm-item">
        <div class="shop-comm-top">
          <div class="shop-comm-when">${escapeHtml(when)}</div>
          <div class="shop-meta">${person} ${phone}</div>
        </div>
        ${note}
      </div>
    `;
  }

  function renderInventoryRow(r) {
    const title = r.product_name || '';
    const tail = [r.size, r.color].filter(Boolean).join(' • ');
    const stats = `Наявно: ${r.available} • Продано: ${r.sold} • Отримано: ${r.received}`;
    return `
      <div class="inv-row" data-product="${escapeHtml(title)}" data-size="${escapeHtml(r.size || '')}" data-color="${escapeHtml(r.color || '')}" data-category="${escapeHtml(r.category || '')}">
        <div class="inv-row-head">
          <div class="inv-name">${escapeHtml(title)}${tail ? ` <span class="shop-muted">• ${escapeHtml(tail)}</span>` : ''}</div>
          <div class="inv-stats">${escapeHtml(stats)}</div>
        </div>
        <div class="inv-actions">
          <button type="button" class="btn-ghost small" data-inv-action="sale">Продано</button>
          <button type="button" class="btn-ghost small" data-inv-action="adjust">Коригувати</button>
        </div>
      </div>
    `;
  }

  async function openManageModal(shopId) {
    currentShopId = shopId;
    manageTitle.textContent = 'Менеджмент магазину';
    manageCommList.innerHTML = '<div class="shop-muted">Завантаження…</div>';
    manageInventory.innerHTML = '<div class="shop-muted">Завантаження…</div>';
    openModal(manageModal);
    try {
      const detail = await fetchShopDetail(shopId);
      const shop = detail.shop || {};
      manageTitle.textContent = `Менеджмент: ${shop.name || ''}`;

      document.getElementById('shop-next-contact-at').value = isoToDateTimeLocal(shop.next_contact_at || '');

      const comms = detail.communications || [];
      manageCommList.innerHTML = comms.length ? comms.map(renderCommItem).join('') : '<div class="shop-muted">Немає записів</div>';

      const inv = detail.inventory || [];
      manageInventory.innerHTML = inv.length ? inv.map(renderInventoryRow).join('') : '<div class="shop-muted">Немає позицій (додайте накладні або коригування)</div>';

      // set defaults for comm form
      document.getElementById('comm_contacted_at').value = isoToDateTimeLocal(new Date().toISOString());
      document.getElementById('comm_person').value = '';
      document.getElementById('comm_phone').value = (shop.phones || []).find((p) => p.is_primary)?.phone || '';
      document.getElementById('comm_note').value = '';
    } catch (err) {
      manageCommList.innerHTML = `<div class="shop-muted">${escapeHtml(err.message || 'Помилка')}</div>`;
      manageInventory.innerHTML = '';
    }
  }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify(payload || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!data.ok) throw new Error(data.error || 'Помилка');
    return data;
  }

  document.getElementById('comm_add_btn').addEventListener('click', async () => {
    if (!currentShopId) return;
    try {
      const contactedAt = document.getElementById('comm_contacted_at').value || '';
      const contactPerson = document.getElementById('comm_person').value || '';
      const phone = document.getElementById('comm_phone').value || '';
      const note = document.getElementById('comm_note').value || '';
      await postJson('/shops/api/contact/add/', {
        shop_id: currentShopId,
        contacted_at: contactedAt,
        contact_person: contactPerson,
        phone,
        note,
      });
      await openManageModal(currentShopId);
    } catch (err) {
      alert(err.message || 'Помилка');
    }
  });

  document.getElementById('shop-next-contact-save').addEventListener('click', async () => {
    if (!currentShopId) return;
    try {
      const nextAt = document.getElementById('shop-next-contact-at').value || '';
      await postJson('/shops/api/next-contact/', { shop_id: currentShopId, next_contact_at: nextAt });
      await openManageModal(currentShopId);
    } catch (err) {
      alert(err.message || 'Помилка');
    }
  });

  document.getElementById('shop-next-contact-clear').addEventListener('click', async () => {
    if (!currentShopId) return;
    try {
      await postJson('/shops/api/next-contact/', { shop_id: currentShopId, next_contact_at: '' });
      await openManageModal(currentShopId);
    } catch (err) {
      alert(err.message || 'Помилка');
    }
  });

  manageInventory.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-inv-action]');
    if (!btn) return;
    const row = btn.closest('.inv-row');
    if (!row || !currentShopId) return;
    const action = btn.dataset.invAction;
    const productName = row.dataset.product || '';
    const size = row.dataset.size || '';
    const color = row.dataset.color || '';
    const category = row.dataset.category || '';

    try {
      if (action === 'sale') {
        const qty = parseInt(prompt('Скільки продано? (число)', '1') || '0', 10);
        if (!qty || qty <= 0) return;
        await postJson('/shops/api/inventory/move/', {
          shop_id: currentShopId,
          kind: 'sale',
          product_name: productName,
          size,
          color,
          category,
          qty,
          note: 'Продано',
        });
      } else if (action === 'adjust') {
        const delta = parseInt(prompt('Коригування кількості (можна зі знаком +/-)', '1') || '0', 10);
        if (!delta) return;
        await postJson('/shops/api/inventory/move/', {
          shop_id: currentShopId,
          kind: 'adjust',
          product_name: productName,
          size,
          color,
          category,
          delta_qty: delta,
          note: 'Коригування',
        });
      }
      await openManageModal(currentShopId);
    } catch (err) {
      alert(err.message || 'Помилка');
    }
  });

  async function deleteShop(shopId) {
    if (!confirm('Видалити магазин? Це може зробити лише адміністратор.')) return;
    try {
      const res = await fetch(`/shops/api/${shopId}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || 'Помилка видалення');
      window.location.reload();
    } catch (err) {
      alert(err.message || 'Помилка');
    }
  }
});

