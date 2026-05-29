/* TwoComms Finance — AI радник: чат + інструменти перевірки (rule-based). */
(function () {
  'use strict';
  var form = document.getElementById('fin-ai-form');
  if (!form) return;

  function csrf() { var m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ''; }
  function api(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: body ? JSON.stringify(body) : '{}' }).then(function (r) { return r.json(); });
  }

  var messages = document.getElementById('fin-ai-messages');
  var input = document.getElementById('fin-ai-question');

  function addMsg(text, who) {
    var welcome = messages.querySelector('.fin-ai-welcome');
    if (welcome) welcome.remove();
    var div = document.createElement('div');
    div.className = 'fin-ai-msg fin-ai-msg--' + who;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function ask(question) {
    addMsg(question, 'user');
    var thinking = addMsg('…', 'bot');
    api('/api/ai/chat/', { question: question }).then(function (d) {
      thinking.textContent = d.ok ? d.answer : (d.error || 'Помилка');
    }).catch(function () { thinking.textContent = 'Помилка мережі'; });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    input.value = '';
    ask(q);
  });

  document.querySelectorAll('.fin-ai-card').forEach(function (c) {
    c.addEventListener('click', function () { ask(c.dataset.prompt); });
  });

  function runCheck(url, label) {
    addMsg(label, 'user');
    var thinking = addMsg('Перевіряю…', 'bot');
    api(url).then(function (d) {
      thinking.remove();
      if (!d.ok) { addMsg('Помилка', 'bot'); return; }
      var wrap = document.createElement('div');
      wrap.className = 'fin-ai-msg fin-ai-msg--bot fin-ai-issues';
      d.issues.forEach(function (i) {
        var row = document.createElement('div');
        row.className = 'fin-ai-issue fin-ai-issue--' + i.level;
        row.textContent = i.text;
        wrap.appendChild(row);
      });
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
    });
  }

  document.querySelectorAll('.fin-ai-menu__item[data-tool]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.fin-ai-menu__item').forEach(function (x) { x.classList.remove('is-active'); });
      b.classList.add('is-active');
      var tool = b.dataset.tool;
      if (tool === 'check_payments') runCheck('/api/ai/check-payments/', 'Перевірити платежі');
      else if (tool === 'check_report') runCheck('/api/ai/check-report/', 'Перевірити звіт');
    });
  });
})();
