/**
 * Dropshipper Auth Modal - Модальное окно входа/регистрации
 */

(function() {
  'use strict';

  const modal = document.getElementById('dsAuthModal');
  if (!modal) return;

  const loginForm = document.getElementById('dsLoginForm');
  const registerForm = document.getElementById('dsRegisterForm');
  const loginFormSubmit = document.getElementById('loginFormSubmit');
  const registerFormSubmit = document.getElementById('registerFormSubmit');

  // Открыть модальное окно
  window.openDsAuthModal = function(mode = 'login') {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    if (mode === 'register') {
      switchForm('register');
    } else {
      switchForm('login');
    }
  };

  // Закрыть модальное окно
  function closeDsAuthModal() {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }

  // Обработчики закрытия
  modal.querySelectorAll('[data-close-modal]').forEach(el => {
    el.addEventListener('click', closeDsAuthModal);
  });

  // Закрытие по Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display === 'flex') {
      closeDsAuthModal();
    }
  });

  // Переключение между формами
  function switchForm(targetForm) {
    const currentForm = loginForm.style.display !== 'none' ? loginForm : registerForm;
    const nextForm = targetForm === 'login' ? loginForm : registerForm;

    if (currentForm === nextForm) return;

    // Анимация выхода
    currentForm.classList.add('ds-auth-form--exiting');
    
    setTimeout(() => {
      currentForm.style.display = 'none';
      currentForm.classList.remove('ds-auth-form--exiting');
      
      // Анимация входа
      nextForm.style.display = 'block';
      nextForm.classList.add('ds-auth-form--entering');
      
      setTimeout(() => {
        nextForm.classList.remove('ds-auth-form--entering');
      }, 300);
    }, 300);
  }

  // Кнопки переключения форм
  modal.querySelectorAll('[data-switch-to]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.switchTo;
      switchForm(target);
    });
  });

  // Показать/скрыть пароль
  modal.querySelectorAll('[data-toggle-password]').forEach(btn => {
    btn.addEventListener('click', () => {
      const inputId = btn.dataset.togglePassword;
      const input = document.getElementById(inputId);
      const icon = btn.querySelector('i');
      
      if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      }
    });
  });

  // Валидация сложности пароля
  const registerPassword = document.getElementById('registerPassword');
  const strengthFill = document.getElementById('passwordStrengthFill');
  const strengthText = document.getElementById('passwordStrengthText');

  if (registerPassword && strengthFill && strengthText) {
    registerPassword.addEventListener('input', () => {
      const password = registerPassword.value;
      const strength = calculatePasswordStrength(password);
      
      // Удаляем все классы
      strengthFill.classList.remove('weak', 'medium', 'strong');
      
      if (password.length === 0) {
        strengthFill.style.width = '0';
        strengthText.textContent = 'Введіть пароль';
        strengthText.style.color = '';
      } else if (strength.score < 40) {
        strengthFill.classList.add('weak');
        strengthText.textContent = 'Слабкий пароль';
        strengthText.style.color = '#ef4444';
      } else if (strength.score < 70) {
        strengthFill.classList.add('medium');
        strengthText.textContent = 'Середній пароль';
        strengthText.style.color = '#f59e0b';
      } else {
        strengthFill.classList.add('strong');
        strengthText.textContent = 'Надійний пароль!';
        strengthText.style.color = '#10b981';
      }
    });
  }

  // Функция расчета сложности пароля
  function calculatePasswordStrength(password) {
    let score = 0;
    
    if (password.length >= 8) score += 20;
    if (password.length >= 12) score += 10;
    if (password.length >= 16) score += 10;
    
    if (/[a-z]/.test(password)) score += 15;
    if (/[A-Z]/.test(password)) score += 15;
    if (/[0-9]/.test(password)) score += 15;
    if (/[^a-zA-Z0-9]/.test(password)) score += 15;
    
    const uniqueChars = new Set(password).size;
    if (uniqueChars > 6) score += 10;
    
    return { score, level: score < 40 ? 'weak' : score < 70 ? 'medium' : 'strong' };
  }

  // AJAX вход
  if (loginFormSubmit) {
    loginFormSubmit.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const submitBtn = loginFormSubmit.querySelector('.ds-auth-submit');
      const loader = submitBtn.querySelector('.ds-auth-submit-loader');
      const errorDiv = document.getElementById('loginError');
      
      // Показать загрузку
      submitBtn.disabled = true;
      loader.style.display = 'block';
      errorDiv.style.display = 'none';
      
      try {
        const formData = new FormData(loginFormSubmit);
        
        const response = await fetch('/accounts/ajax/login/', {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          }
        });
        
        const data = await response.json();
        
        if (data.success) {
          // Успешный вход - перезагрузить страницу
          window.location.reload();
        } else {
          // Показать ошибку
          errorDiv.textContent = data.error || 'Невірний логін або пароль';
          errorDiv.style.display = 'block';
          submitBtn.disabled = false;
          loader.style.display = 'none';
        }
      } catch (error) {
        console.error('Login error:', error);
        errorDiv.textContent = 'Помилка з\'єднання. Спробуйте ще раз.';
        errorDiv.style.display = 'block';
        submitBtn.disabled = false;
        loader.style.display = 'none';
      }
    });
  }

  // AJAX регистрация
  if (registerFormSubmit) {
    registerFormSubmit.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const submitBtn = registerFormSubmit.querySelector('.ds-auth-submit');
      const loader = submitBtn.querySelector('.ds-auth-submit-loader');
      const errorDiv = document.getElementById('registerError');
      
      // Проверка совпадения паролей
      const password1 = document.getElementById('registerPassword').value;
      const password2 = document.getElementById('registerPassword2').value;
      
      if (password1 !== password2) {
        errorDiv.textContent = 'Паролі не співпадають';
        errorDiv.style.display = 'block';
        return;
      }
      
      // Показать загрузку
      submitBtn.disabled = true;
      loader.style.display = 'block';
      errorDiv.style.display = 'none';
      
      try {
        const formData = new FormData(registerFormSubmit);
        
        const response = await fetch('/accounts/ajax/register/', {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          }
        });
        
        const data = await response.json();
        
        if (data.success) {
          // Успешная регистрация - перезагрузить страницу
          window.location.reload();
        } else {
          // Показать ошибки
          let errorMsg = data.error || 'Помилка реєстрації';
          if (data.errors) {
            errorMsg = Object.values(data.errors).flat().join(' ');
          }
          errorDiv.textContent = errorMsg;
          errorDiv.style.display = 'block';
          submitBtn.disabled = false;
          loader.style.display = 'none';
        }
      } catch (error) {
        console.error('Registration error:', error);
        errorDiv.textContent = 'Помилка з\'єднання. Спробуйте ще раз.';
        errorDiv.style.display = 'block';
        submitBtn.disabled = false;
        loader.style.display = 'none';
      }
    });
  }

  // Открыть модальное окно при клике на кнопки входа
  document.addEventListener('click', (e) => {
    // Обработка кнопок с data-open-auth-modal
    if (e.target.matches('[data-open-auth-modal]') || e.target.closest('[data-open-auth-modal]')) {
      e.preventDefault();
      const btn = e.target.matches('[data-open-auth-modal]') ? e.target : e.target.closest('[data-open-auth-modal]');
      const mode = btn.dataset.openAuthModal || 'login';
      openDsAuthModal(mode);
      return;
    }
    
    // Обработка элементов с data-require-auth (защищенные кнопки/ссылки)
    if (e.target.matches('[data-require-auth="true"]') || e.target.closest('[data-require-auth="true"]')) {
      e.preventDefault();
      e.stopPropagation();
      openDsAuthModal('login');
      return;
    }
  });

})();

