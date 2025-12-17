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

function initManagementShopsPage() {
  const body = document.body;
  const shopsDataEl = document.getElementById('shops-data');
  const shopsGridRoot = document.getElementById('shops-grid');
  const shopForm = document.getElementById('shop-form');
  if (!shopsDataEl || !shopsGridRoot || !shopForm) return;
  if (shopsGridRoot.dataset.mgmtInitialized === '1') return;
  shopsGridRoot.dataset.mgmtInitialized = '1';

  const shops = JSON.parse(shopsDataEl.textContent || '[]');

  const testProductsDataEl = document.getElementById('test-products-data');
  const testProducts = testProductsDataEl ? JSON.parse(testProductsDataEl.textContent || '[]') : [];

  const shopModal = document.getElementById('shop-modal');
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
      const contractInput = document.getElementById('test_contract_file');
      if (contractInput) contractInput.value = '';
      const contractCurrent = document.getElementById('test-contract-current');
      if (contractCurrent) { contractCurrent.style.display = 'none'; contractCurrent.innerHTML = ''; }
    }
    applyShipmentsForShopType();
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
        <div class="field shipment-invoice-kind-wrap">
          <label>Накладна</label>
          <select class="shipment-invoice-kind">
            <option value="none">—</option>
            <option value="system">Вибрати з накладних</option>
            <option value="upload">Завантажити Excel</option>
          </select>
        </div>
        <div class="field shipment-test-hint" style="display:none;">
          <label>Накладна</label>
          <div class="shop-muted">Для тестового магазину накладна не потрібна — прикріпіть договір у блоці «Тестовий магазин».</div>
        </div>
        <div class="field shipment-invoice-system" style="display:none;">
          <label>Накладна (система)</label>
          <select class="shipment-invoice-select"></select>
        </div>
        <div class="field shipment-invoice-upload" style="display:none;">
          <label>Excel</label>
          <input type="file" class="shipment-invoice-file" name="${fileField}" accept=".xlsx,.xlsm,.xls" />
        </div>
      </div>
      <div class="row-actions">
        <div class="shipment-current" style="flex:1; color: var(--text-secondary); font-size: 0.9rem;"></div>
        <button type="button" class="btn-ghost small danger shipment-remove">Видалити</button>
      </div>
    `;

    el.querySelector('.shipment-ttn').value = ttn;
    el.querySelector('.shipment-date').value = shippedAt ? shippedAt.slice(0, 10) : '';

    const kindSel = el.querySelector('.shipment-invoice-kind');
    const kindWrap = el.querySelector('.shipment-invoice-kind-wrap');
    const testHint = el.querySelector('.shipment-test-hint');
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

    el.applyShopType = (shopType) => {
      const isTestShop = shopType === 'test';
      if (testHint) testHint.style.display = isTestShop ? '' : 'none';
      if (kindWrap) kindWrap.style.display = isTestShop ? 'none' : '';
      kindSel.disabled = isTestShop;
      if (isTestShop) {
        kindSel.value = 'none';
        sysWrap.style.display = 'none';
        upWrap.style.display = 'none';
        invSel.value = '';
        el.querySelector('.shipment-invoice-file').value = '';
      }
    };

    el.querySelector('.shipment-remove').addEventListener('click', () => {
      el.remove();
      ensureAtLeastOneShipment();
    });

    return el;
  }

  function ensureAtLeastOneShipment() {
    if (!shipmentsWrap.querySelector('.shipment-row')) {
      shipmentsWrap.appendChild(renderShipmentRow({ invoice_kind: 'none' }));
      applyShipmentsForShopType();
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
    applyShipmentsForShopType();
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
    const contractInput = document.getElementById('test_contract_file');
    if (contractInput) contractInput.value = '';
    const contractCurrent = document.getElementById('test-contract-current');
    if (contractCurrent) { contractCurrent.style.display = 'none'; contractCurrent.innerHTML = ''; }
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
      const contractCurrent = document.getElementById('test-contract-current');
      if (contractCurrent) {
        const dl = shop.test_contract_download_url ? `<a href="${escapeHtml(shop.test_contract_download_url)}" target="_blank" rel="noopener">скачати</a>` : '';
        const name = shop.test_contract_name ? escapeHtml(shop.test_contract_name) : 'немає';
        contractCurrent.style.display = '';
        contractCurrent.innerHTML = `Поточний договір: <b>${name}</b>${dl ? ` • ${dl}` : ''}`;
      }
    }

    phonesWrap.innerHTML = '';
    (shop.phones || []).forEach((p) => phonesWrap.appendChild(renderPhoneRow(p)));
    ensureAtLeastOnePhone();
    ensureOnePrimaryPhone();

    try { await ensureInvoicesLoaded(); } catch (e) {}
    shipmentsWrap.innerHTML = '';
    (shop.shipments || []).forEach((s) => shipmentsWrap.appendChild(renderShipmentRow(s)));
    ensureAtLeastOneShipment();
    applyShipmentsForShopType();

    openModal(shopModal);
  }

  const addCard = document.getElementById('shop-add-card');
  if (addCard) addCard.addEventListener('click', openCreateShop);

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
    const isTestShop = shopForm.querySelector('input[name="shop_type"]:checked')?.value === 'test';
    rows.forEach((row, idx) => {
      const ttn = row.querySelector('.shipment-ttn').value || '';
      const date = row.querySelector('.shipment-date').value || '';
      if (!ttn.trim() || !date.trim()) return;
      const kind = isTestShop ? 'none' : (row.querySelector('.shipment-invoice-kind').value || 'none');
      const invSel = row.querySelector('.shipment-invoice-select');
      const fileInput = row.querySelector('.shipment-invoice-file');

      const payload = {
        id: row.dataset.shipmentId ? parseInt(row.dataset.shipmentId, 10) : undefined,
        ttn_number: ttn.trim(),
        shipped_at: date,
        invoice_kind: kind,
      };

      if (!isTestShop) {
        if (kind === 'system') {
          payload.wholesale_invoice_id = invSel.value ? parseInt(invSel.value, 10) : null;
        } else if (kind === 'upload') {
          if (fileInput.files && fileInput.files[0]) {
            payload.file_field = row.dataset.fileField;
          } else {
            payload.file_field = '';
          }
        }
      }

      data.push(payload);
    });

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
    if (s.invoice_kind === 'none' && !items.length) {
      lines.push(`<div class="shop-muted">Накладної немає</div>`);
    } else if (items.length) {
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
    invoicesTitle.textContent = 'Документи магазину';
    invoicesBody.innerHTML = '<div class="shop-muted">Завантаження…</div>';
    openModal(invoicesModal);
    try {
      const detail = await fetchShopDetail(shopId);
      const shop = detail.shop || {};
      invoicesTitle.textContent = `Документи: ${shop.name || ''}`;
      const shipments = detail.shipments || [];
      const blocks = [];
      if (shop.shop_type === 'test') {
        const contract = shop.test_contract_download_url
          ? `<a class="btn-ghost small" href="${escapeHtml(shop.test_contract_download_url)}" target="_blank" rel="noopener">Скачати договір</a>`
          : '';
        const contractName = shop.test_contract_name ? escapeHtml(shop.test_contract_name) : '—';
        blocks.push(`
          <div class="shipment-card">
            <div class="shipment-head">
              <div>
                <div class="shipment-title">Договір</div>
                <div class="shipment-meta">${contractName}</div>
              </div>
              <div>${contract}</div>
            </div>
            ${contract ? '' : '<div class="shipment-items"><div class="shop-muted">Договір не прикріплено</div></div>'}
          </div>
        `);
      }
      if (!shipments.length) {
        blocks.push('<div class="shop-muted">Немає ТТН</div>');
      } else {
        blocks.push(shipments.map(renderShipmentSummaryCard).join(''));
      }
      invoicesBody.innerHTML = blocks.join('');
    } catch (err) {
      invoicesBody.innerHTML = `<div class="shop-muted">${escapeHtml(err.message || 'Помилка')}</div>`;
    }
  }

  function applyShipmentsForShopType() {
    const shopType = shopForm.querySelector('input[name="shop_type"]:checked')?.value || 'full';
    shipmentsWrap.querySelectorAll('.shipment-row').forEach((row) => {
      if (typeof row.applyShopType === 'function') row.applyShopType(shopType);
    });
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

  let inventoryGroups = [];

  const SIZE_ORDER = ['XXXS','XXS','XS','S','M','L','XL','XXL','XXXL','4XL','5XL','6XL'];
  function sizeRank(sizeRaw) {
    const s = String(sizeRaw || '').trim().toUpperCase();
    if (!s) return 10_000;
    const idx = SIZE_ORDER.indexOf(s);
    if (idx >= 0) return idx;
    const num = parseFloat(s.replace(',', '.'));
    if (!Number.isNaN(num)) return 5000 + num;
    return 9000 + s.charCodeAt(0);
  }

  function buildInventoryGroups(rows) {
    const map = new Map();
    (rows || []).forEach((r) => {
      const productName = String(r.product_name || '').trim();
      const category = String(r.category || '').trim();
      const color = String(r.color || '').trim();
      const key = `${category}||${productName}||${color}`;
      if (!map.has(key)) {
        map.set(key, {
          id: 0,
          key,
          product_name: productName,
          category,
          color,
          sizes: [],
          totals: { available: 0, sold: 0, received: 0 },
          search: '',
        });
      }
      const g = map.get(key);
      g.sizes.push({
        size: String(r.size || '').trim(),
        available: Number(r.available || 0),
        sold: Number(r.sold || 0),
        received: Number(r.received || 0),
      });
    });

    const groups = Array.from(map.values());
    groups.forEach((g, idx) => {
      g.id = idx;
      g.sizes.sort((a, b) => sizeRank(a.size) - sizeRank(b.size));
      g.totals = g.sizes.reduce((acc, s) => {
        acc.available += s.available || 0;
        acc.sold += s.sold || 0;
        acc.received += s.received || 0;
        return acc;
      }, { available: 0, sold: 0, received: 0 });
      g.search = `${g.product_name} ${g.category} ${g.color}`.toLowerCase();
    });
    groups.sort((a, b) => (a.category + a.product_name).localeCompare(b.category + b.product_name));
    return groups;
  }

  function renderInventory(groups) {
    const toolbar = `
      <div class="inv-toolbar">
        <input type="search" id="inv-search" placeholder="Пошук товару / категорії / кольору…" />
      </div>
    `;
    const cards = (groups || []).map((g) => {
      const meta = [g.category, g.color].filter(Boolean).join(' • ');
      const totals = `Наявно: ${g.totals.available} • Продано: ${g.totals.sold} • Отримано: ${g.totals.received}`;
      const sizePills = (g.sizes || []).map((s) => {
        const label = s.size || '—';
        return `<span class="inv-size-pill"><span>${escapeHtml(label)}</span><span class="count">${escapeHtml(String(s.available || 0))}</span></span>`;
      }).join('');
      return `
        <div class="inv-group" data-inv-group-id="${g.id}" data-inv-search="${escapeHtml(g.search)}">
          <div class="inv-group-head">
            <div>
              <div class="inv-group-name">${escapeHtml(g.product_name || '—')}</div>
              ${meta ? `<div class="inv-group-meta">${escapeHtml(meta)}</div>` : ''}
            </div>
            <div class="inv-group-totals">${escapeHtml(totals)}</div>
          </div>
          <div class="inv-size-grid">${sizePills || '<div class="shop-muted">Немає розмірів</div>'}</div>
          <div class="inv-group-actions">
            <button type="button" class="btn-ghost small" data-inv-group-action="sale">Продати</button>
            <button type="button" class="btn-ghost small" data-inv-group-action="adjust">Коригувати</button>
          </div>
          <div class="inv-editor" style="display:none;"></div>
        </div>
      `;
    }).join('');
    return toolbar + (cards || '<div class="shop-muted">Немає позицій</div>');
  }

  function renderSaleEditor(group) {
    const rows = (group.sizes || []).map((s) => {
      const label = s.size || '—';
      const max = Math.max(0, Number(s.available || 0));
      const sold = Math.max(0, Number(s.sold || 0));
      const received = Math.max(0, Number(s.received || 0));
      return `
        <div class="inv-sale-row">
          <div class="inv-sale-size">${escapeHtml(label)}</div>
          <div class="inv-sale-available">Наявно: ${escapeHtml(String(max))} • Продано: ${escapeHtml(String(sold))} • Отримано: ${escapeHtml(String(received))}</div>
          <input type="number" class="inv-sale-qty" data-size="${escapeHtml(s.size || '')}" min="0" max="${escapeHtml(String(max))}" value="0" />
        </div>
      `;
    }).join('');

    return `
      <div class="inv-editor-card" data-inv-editor="sale">
        <div class="inv-editor-head">
          <div class="inv-editor-title">Продаж (вкажіть розміри)</div>
          <button type="button" class="btn-ghost small" data-inv-editor-cancel>Скасувати</button>
        </div>
        <div class="inv-sale-grid">${rows || '<div class="shop-muted">Немає розмірів для продажу</div>'}</div>
        <div class="inv-sale-total" data-inv-sale-total>Разом: 0</div>
        <div class="inv-editor-actions">
          <button type="button" class="btn-primary" data-inv-editor-submit="sale">Зберегти продаж</button>
        </div>
      </div>
    `;
  }

  function renderAdjustEditor(group) {
    const opts = (group.sizes || []).map((s) => {
      const label = s.size || '—';
      return `<option value="${escapeHtml(s.size || '')}">${escapeHtml(label)}</option>`;
    }).join('');
    return `
      <div class="inv-editor-card" data-inv-editor="adjust">
        <div class="inv-editor-head">
          <div class="inv-editor-title">Коригування залишків</div>
          <button type="button" class="btn-ghost small" data-inv-editor-cancel>Скасувати</button>
        </div>
        <div class="field-grid">
          <div class="field">
            <label>Розмір</label>
            <select class="inv-adjust-size">${opts || '<option value="">—</option>'}</select>
          </div>
          <div class="field">
            <label>Коригування (+/-)</label>
            <input type="number" class="inv-adjust-delta" value="1" />
          </div>
          <div class="field field-span-2">
            <label>Нотатка</label>
            <input type="text" class="inv-adjust-note" placeholder="Напр.: повернення, пересорт…" />
          </div>
        </div>
        <div class="inv-editor-actions">
          <button type="button" class="btn-primary" data-inv-editor-submit="adjust">Зберегти коригування</button>
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
      inventoryGroups = buildInventoryGroups(inv);
      manageInventory.innerHTML = inventoryGroups.length ? renderInventory(inventoryGroups) : '<div class="shop-muted">Немає позицій (додайте накладні або коригування)</div>';
      const search = manageInventory.querySelector('#inv-search');
      if (search) {
        search.addEventListener('input', () => {
          const q = (search.value || '').trim().toLowerCase();
          manageInventory.querySelectorAll('.inv-group').forEach((el) => {
            const text = (el.dataset.invSearch || '').toLowerCase();
            el.style.display = !q || text.includes(q) ? '' : 'none';
          });
        });
      }

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

  function getInvGroupFromEl(el) {
    const groupEl = el.closest('.inv-group');
    if (!groupEl) return { groupEl: null, group: null };
    const id = parseInt(groupEl.dataset.invGroupId || '', 10);
    const group = inventoryGroups.find((g) => g.id === id) || null;
    return { groupEl, group };
  }

  function closeAllInvEditors(exceptGroupEl) {
    manageInventory.querySelectorAll('.inv-group .inv-editor').forEach((ed) => {
      const host = ed.closest('.inv-group');
      if (exceptGroupEl && host === exceptGroupEl) return;
      ed.style.display = 'none';
      ed.innerHTML = '';
    });
  }

  manageInventory.addEventListener('input', (e) => {
    const qtyInput = e.target.closest('.inv-sale-qty');
    if (!qtyInput) return;
    const editor = qtyInput.closest('[data-inv-editor="sale"]');
    if (!editor) return;
    const totalEl = editor.querySelector('[data-inv-sale-total]');
    if (!totalEl) return;
    let total = 0;
    editor.querySelectorAll('.inv-sale-qty').forEach((inp) => {
      const v = parseInt(inp.value || '0', 10);
      if (v > 0) total += v;
    });
    totalEl.textContent = `Разом: ${total}`;
  });

  manageInventory.addEventListener('click', async (e) => {
    const cancelBtn = e.target.closest('[data-inv-editor-cancel]');
    if (cancelBtn) {
      const editor = cancelBtn.closest('.inv-editor');
      if (editor) { editor.style.display = 'none'; editor.innerHTML = ''; }
      return;
    }

    const groupActionBtn = e.target.closest('button[data-inv-group-action]');
    if (groupActionBtn) {
      const { groupEl, group } = getInvGroupFromEl(groupActionBtn);
      if (!groupEl || !group || !currentShopId) return;
      const action = groupActionBtn.dataset.invGroupAction;
      const editor = groupEl.querySelector('.inv-editor');
      if (!editor) return;
      closeAllInvEditors(groupEl);
      editor.style.display = '';
      if (action === 'sale') {
        editor.innerHTML = renderSaleEditor(group);
      } else if (action === 'adjust') {
        editor.innerHTML = renderAdjustEditor(group);
      }
      return;
    }

    const submitBtn = e.target.closest('button[data-inv-editor-submit]');
    if (!submitBtn) return;
    const { groupEl, group } = getInvGroupFromEl(submitBtn);
    if (!groupEl || !group || !currentShopId) return;
    const mode = submitBtn.dataset.invEditorSubmit;
    const editor = groupEl.querySelector('.inv-editor');
    if (!editor) return;

    try {
      if (mode === 'sale') {
        const lines = [];
        editor.querySelectorAll('.inv-sale-qty').forEach((inp) => {
          const qty = parseInt(inp.value || '0', 10);
          if (!qty || qty <= 0) return;
          lines.push({ size: inp.dataset.size || '', qty });
        });
        if (!lines.length) return;
        submitBtn.disabled = true;
        await postJson('/shops/api/inventory/move/', {
          shop_id: currentShopId,
          kind: 'sale',
          product_name: group.product_name,
          category: group.category,
          color: group.color,
          note: 'Продано',
          lines,
        });
      } else if (mode === 'adjust') {
        const size = editor.querySelector('.inv-adjust-size')?.value || '';
        const delta = parseInt(editor.querySelector('.inv-adjust-delta')?.value || '0', 10);
        const note = editor.querySelector('.inv-adjust-note')?.value || '';
        if (!delta) return;
        submitBtn.disabled = true;
        await postJson('/shops/api/inventory/move/', {
          shop_id: currentShopId,
          kind: 'adjust',
          product_name: group.product_name,
          category: group.category,
          color: group.color,
          size,
          delta_qty: delta,
          note: note.trim() || 'Коригування',
        });
      }

      await openManageModal(currentShopId);
    } catch (err) {
      alert(err.message || 'Помилка');
      submitBtn.disabled = false;
    }
  });

  async function deleteShop(shopId) {
    const shop = shops.find((x) => String(x.id) === String(shopId));
    const canDelete = !!(shop && shop.can_delete);
    if (!canDelete) {
      const ok = confirm('У вас недостатньо прав для видалення магазину. Зверніться до адміністратора.\n\nНатисніть OK, щоб перейти в Telegram.');
      if (ok) window.location.href = 'https://telegram.com';
      return;
    }

    if (!confirm('Видалити магазин?')) return;
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
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initManagementShopsPage);
} else {
  initManagementShopsPage();
}
