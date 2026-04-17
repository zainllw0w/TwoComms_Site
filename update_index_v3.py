import sys
import re

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

css_replacement = """    /* NEW SURVEY CSS V3 */
    .survey-container-v3 {
      display: grid;
      gap: 1.25rem;
      margin: 1rem 0;
    }
    @media (min-width: 900px) {
      .survey-container-v3 {
        grid-template-columns: 280px 1fr;
      }
    }

    .survey-panel-dark {
      background: linear-gradient(135deg, #38160d, #1c0602);
      border-radius: 20px;
      padding: 1.25rem;
      border: 1px solid rgba(255, 140, 66, 0.15);
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }

    /* Left Panel */
    .sl-header {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1rem;
    }
    .sl-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, rgba(255,140,66,0.3), rgba(255,209,140,0.1));
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ff9b55;
      position: relative;
    }
    .sl-icon::after {
      content: '';
      position: absolute;
      top: 50%; left: 50%; transform: translate(-50%, -50%);
      width: 28px; height: 28px;
      background: #1a0c06;
      border-radius: 50%;
      z-index: 1;
    }
    .sl-icon svg {
      position: relative;
      z-index: 2;
    }
    .sl-bonus-info {
      display: flex;
      flex-direction: column;
    }
    .sl-kicker {
      font-size: 0.65rem;
      font-weight: 700;
      text-transform: uppercase;
      color: rgba(255, 255, 255, 0.6);
      letter-spacing: 0.05em;
      margin-bottom: 0.2rem;
    }
    .sl-amount {
      font-size: 1.4rem;
      font-weight: 900;
      color: #fff;
      line-height: 1;
    }
    .sl-desc {
      font-size: 0.85rem;
      color: rgba(255, 255, 255, 0.7);
      line-height: 1.4;
      margin-bottom: 1.25rem;
    }
    .sl-tags {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .sl-tag {
      background: rgba(0, 0, 0, 0.3);
      padding: 0.5rem 0.8rem;
      border-radius: 8px;
      font-size: 0.75rem;
      color: rgba(255, 255, 255, 0.8);
      font-weight: 500;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* Right Panel */
    .survey-right-panel {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .sr-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }
    .sr-title {
      margin: 0;
      color: #fff;
      font-size: clamp(1.2rem, 2vw, 1.5rem);
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    .sr-subtitle {
      margin: 0.25rem 0 0 0;
      color: rgba(255, 255, 255, 0.7);
      font-size: 0.85rem;
    }
    .sr-dismiss {
      background: rgba(255, 163, 102, 1);
      color: #1a0c06;
      border: none;
      padding: 0.4rem 0.8rem;
      border-radius: 8px;
      font-weight: 800;
      font-size: 0.7rem;
      cursor: pointer;
      text-transform: uppercase;
      white-space: nowrap;
      transition: opacity 0.2s;
    }
    .sr-dismiss:hover { opacity: 0.9; }

    .sr-banner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: relative;
      overflow: hidden;
    }
    .sr-banner-text {
      position: relative;
      z-index: 2;
      max-width: 28rem;
    }
    .sr-banner-title {
      margin: 0;
      font-size: clamp(1.5rem, 2.5vw, 2.2rem);
      font-weight: 900;
      line-height: 1.1;
      color: #fff;
      text-transform: uppercase;
      letter-spacing: -0.01em;
    }
    .sr-banner-desc {
      margin: 0.5rem 0 0 0;
      color: rgba(255, 255, 255, 0.85);
      font-size: 0.9rem;
      line-height: 1.4;
    }
    .sr-banner-icon {
      position: relative;
      z-index: 1;
    }

    .sr-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .sr-footer-pills {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .sr-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.3rem 0.7rem;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      font-size: 0.75rem;
      color: rgba(255, 255, 255, 0.75);
      background: rgba(255, 255, 255, 0.03);
      white-space: nowrap;
    }
    .sr-pill-dot {
      width: 5px; height: 5px;
      background: #ffaa55;
      border-radius: 50%;
    }
    .sr-cta {
      background: linear-gradient(135deg, #ff9b55, #ffb347);
      color: #1a0c06;
      border: none;
      padding: 0.7rem 1.5rem;
      border-radius: 10px;
      font-weight: 800;
      font-size: 0.9rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      box-shadow: 0 4px 15px rgba(255, 140, 66, 0.3);
      transition: transform 0.2s ease;
      white-space: nowrap;
    }
    .sr-cta:hover { transform: translateY(-2px); }

    @media (max-width: 900px) {
      .sr-header-row {
        flex-direction: column;
      }
      .sr-dismiss {
        align-self: flex-start;
      }
    }
    @media (max-width: 600px) {
      .sr-banner {
        flex-direction: column;
        align-items: flex-start;
        gap: 1rem;
      }
      .sr-banner-icon {
        margin-left: auto;
        width: 70px; height: 70px;
      }
      .sr-banner-icon svg { width: 100%; height: 100%; }
    }
"""

html_replacement = """    <!-- Скрываемый контент (референсный 2-колоночный дизайн V3) -->
    <div class="featured-content-unified collapsed" id="featured-content" style="display: block; max-height: none; overflow: visible;">
      <div class="survey-container-v3">
        
        <!-- Left Panel -->
        <div class="survey-panel-dark">
          <div class="sl-header">
            <div class="sl-icon">
              <!-- Question mark in bubble SVG -->
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 16h-2v-2h2v2zm.87-7.85l-.95 1.01c-.55.59-.92 1.14-.92 2.34h-2v-.5c0-1.1.45-2.1 1.15-2.85l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.05-.43 2-1.13 2.67z"/>
              </svg>
            </div>
            <div class="sl-bonus-info">
              <span class="sl-kicker">Бонус за фідбек</span>
              <span class="sl-amount">-{{ survey_reward.amount_uah|default:200 }} грн</span>
            </div>
          </div>
          <p class="sl-desc">Промокод активується автоматично одразу після проходження та діє на весь асортимент.</p>
          <div class="sl-tags">
            <div class="sl-tag">≈ 5 хвилин часу</div>
            <div class="sl-tag">Один раз на рік</div>
            <div class="sl-tag">Можна повернутись потім</div>
          </div>
        </div>

        <!-- Right Panel -->
        <div class="survey-right-panel">
          <div class="sr-header-row">
            <div>
              <h2 class="sr-title">Допоможи покращити TWOCOMMS</h2>
              <p class="sr-subtitle">Коротке опитування без довгої анкети: відповіді допоможуть нам стати кращими.</p>
            </div>
            <button type="button" class="sr-dismiss" id="featuredToggle">
              БІЛЬШЕ НЕ ПОКАЗУВАТИ
            </button>
          </div>

          <div class="survey-panel-dark sr-banner">
            <div class="sr-banner-text">
              <h3 class="sr-banner-title">
                ВИГРАЙ {{ survey_reward.amount_uah|default:200 }} ГРН<br>ЗА ОПИТУВАННЯ!
              </h3>
              <p class="sr-banner-desc">
                Дай відповідь на кілька запитань та забери свій промокод!
              </p>
            </div>
            <div class="sr-banner-icon" id="survey-gift-icon-container">
              <!-- ИКОНКА КОРЗИНЫ / ПОДАРУНКА ЗНАХОДИТЬСЯ ТУТ -->
              <svg width="90" height="90" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 0 16px rgba(255,140,66,0.3));">
                <path d="M20 7H16C16 5.89543 15.1046 5 14 5C13.1951 5 12.5013 5.47487 12 6.1499C11.4987 5.47487 10.8049 5 10 5C8.89543 5 8 5.89543 8 7H4C3.44772 7 3 7.44772 3 8V11C3 11.5523 3.44772 12 4 12H5V19C5 19.5523 5.44772 20 6 20H18C18.5523 20 19 19.5523 19 19V12H20C20.5523 12 21 11.5523 21 11V8C21 7.44772 20.5523 7 20 7ZM10 6.5C10.2761 6.5 10.5 6.72386 10.5 7C10.5 7.27614 10.2761 7.5 10 7.5C9.72386 7.5 9.5 7.27614 9.5 7C9.5 6.72386 9.72386 6.5 10 6.5ZM14 6.5C14.2761 6.5 14.5 6.72386 14.5 7C14.5 7.27614 14.2761 7.5 14 7.5C13.7238 7.5 13.5 7.27614 13.5 7C13.5 6.72386 13.7238 6.5 14 6.5ZM11 12V18H7V12H11ZM17 18H13V12H17V18ZM19 10.5H5V8.5H19V10.5Z" fill="url(#giftGrad5)" />
                <defs>
                  <linearGradient id="giftGrad5" x1="12" y1="5" x2="12" y2="20" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#FFD18C" />
                    <stop offset="1" stop-color="#FF8C42" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>

          <div class="sr-footer">
            <div class="sr-footer-pills">
              <span class="sr-pill"><span class="sr-pill-dot"></span> Без форми на одну сторінку</span>
              <span class="sr-pill"><span class="sr-pill-dot"></span> Лише для зареєстрованих користувачів</span>
            </div>
            <button
              type="button"
              class="sr-cta"
              data-survey-cta
              data-survey-key="{{ survey_key }}"
              data-survey-start-text="{{ survey_ui_home.cta_start_uk|default:'Пройти опитування' }}"
              data-survey-continue-text="{{ survey_ui_home.cta_continue_uk|default:'Продовжити опитування' }}"
              data-survey-authenticated="{% if request.user.is_authenticated %}1{% else %}0{% endif %}"
              data-login-url="{% url 'login' %}?next={{ request.path }}"
            >
              <span>Пройти опитування</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
              </svg>
            </button>
          </div>
        </div>

      </div>
    </div>\n"""

# Regex replacing CSS
html = re.sub(r'(?s)\.survey-card-modern \{.*?(?=\.survey-modal \{)', css_replacement, html)

# Regex replacing HTML
html = re.sub(r'(?s)    <!-- Скрываемый контент \(референсный дизайн\) -->.*?</div>\s+</div>\s+</div>', html_replacement, html)

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Updates applied with V3 design.")
