import sys

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

css_replacement = """    .survey-card {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      align-items: stretch;
      padding: 0;
      background: rgba(15, 16, 20, 0.4);
      border-radius: 20px;
    }

    @media (min-width: 768px) {
      .survey-card {
        flex-direction: row;
        align-items: center;
        gap: 1.5rem;
      }
    }

    .survey-signal-compact {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 1rem;
      border-radius: 16px;
      /* Using exact gradient from previous design left block for matching */
      background: radial-gradient(circle at top right, rgba(255, 204, 122, 0.16), transparent 34%), linear-gradient(160deg, rgba(255, 186, 97, 0.24), rgba(255, 140, 66, 0.12) 52%, rgba(10, 11, 17, 0.88));
      border: 1px solid rgba(255, 174, 91, 0.28);
      box-shadow: 0 18px 34px rgba(255, 140, 66, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.14);
      flex: 0 0 auto;
    }

    .survey-signal-ring-compact {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #ffd18c, #ff8c42);
      color: #2a1508;
      box-shadow: 0 12px 24px rgba(255, 140, 66, 0.34);
    }

    .survey-signal-ring-compact svg {
      width: 24px;
      height: 24px;
    }

    .survey-signal-copy-compact {
      display: flex;
      flex-direction: column;
      line-height: 1.1;
    }

    .survey-signal-kicker-compact {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      color: rgba(255, 241, 221, 0.82);
      letter-spacing: 0.05em;
      margin-bottom: 0.2rem;
    }

    .survey-signal-bonus-compact {
      font-size: 1.3rem;
      font-weight: 800;
      color: #fff4e2;
    }

    .survey-signal-pill-compact {
      margin-left: auto;
      padding: 0.36rem 0.72rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: rgba(8, 8, 12, 0.42);
      border: 1px solid rgba(255, 255, 255, 0.14);
      color: rgba(255, 249, 239, 0.92);
      backdrop-filter: blur(10px);
    }

    @media (min-width: 768px) {
      .survey-signal-pill-compact {
        margin-left: 1rem;
      }
    }

    .survey-promo-banner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex: 1;
      padding: 1.25rem 2rem;
      border-radius: 20px;
      background: linear-gradient(135deg, rgba(255, 209, 140, 0.08), rgba(255, 140, 66, 0.03));
      border: 1px solid rgba(255, 186, 97, 0.15);
      position: relative;
      overflow: hidden;
    }

    .survey-promo-content {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      z-index: 1;
      max-width: 32rem;
    }

    .survey-promo-title {
      margin: 0;
      color: #f8f1e6;
      font-size: clamp(1.4rem, 2vw, 1.8rem);
      font-weight: 800;
      line-height: 1.1;
      letter-spacing: -0.02em;
      text-transform: uppercase;
    }

    .survey-promo-subtitle {
      margin: 0;
      color: rgba(255, 255, 255, 0.8);
      font-size: 0.95rem;
      line-height:1.4;
      margin-bottom: 0.75rem;
    }

    .survey-promo-actions {
      display: flex;
      align-items: center;
      gap: 1.2rem;
      flex-wrap: wrap;
    }

    .survey-cta-compact {
      padding: 0.75rem 1.5rem;
      border: none;
      border-radius: 14px;
      background: linear-gradient(135deg, #ff8c42, #ffb347);
      color: #1d130a;
      box-shadow: 0 10px 24px rgba(255, 140, 66, 0.28);
      font-weight: 700;
      font-size: 0.95rem;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    .survey-cta-compact:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 30px rgba(255, 140, 66, 0.36);
    }

    .survey-dismiss-btn {
      background: transparent;
      border: none;
      color: rgba(255, 255, 255, 0.5);
      font-size: 0.85rem;
      text-decoration: underline;
      text-underline-offset: 4px;
      cursor: pointer;
      padding: 0.4rem;
      transition: color 0.2s;
    }

    .survey-dismiss-btn:hover {
      color: rgba(255, 255, 255, 0.8);
    }

    .survey-promo-icon {
      position: absolute;
      right: 2rem;
      top: 50%;
      transform: translateY(-50%);
      opacity: 0.9;
      pointer-events: none;
    }

    @media (max-width: 991px) {
      .survey-promo-icon {
        right: 0.5rem;
        opacity: 0.4;
      }
    }

    @media (max-width: 640px) {
      .survey-promo-banner {
        flex-direction: column;
        align-items: flex-start;
        padding: 1.25rem;
      }
      .survey-promo-icon {
        position: relative;
        right: auto;
        top: auto;
        transform: none;
        margin-top: 1rem;
        margin-left: auto;
        opacity: 0.8;
      }
      .survey-signal-compact {
        flex-wrap: wrap;
      }
      .survey-signal-pill-compact {
        margin-left: 0;
        margin-top: 0.5rem;
        width: 100%;
        text-align: center;
      }
    }
"""

html_replacement = """    <!-- Скрываемый контент (теперь без заголовка, компактный блок) -->
    <div class="featured-content-unified collapsed" id="featured-content" style="display: block; max-height: none; overflow: visible;">
      <div class="survey-card survey-card-modern mb-2 mt-2">
        
        <!-- Left block -->
        <div class="survey-signal-compact">
          <div class="survey-signal-ring-compact">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C6.49 2 2 5.92 2 11c0 2.52 1.09 4.78 2.86 6.38L4 22l4.06-2.2c1.2.33 2.49.5 3.94.5 5.51 0 10-3.92 10-9S17.51 2 12 2zm.1 14.4c-.62 0-1.1-.48-1.1-1.08 0-.63.48-1.12 1.1-1.12.64 0 1.14.49 1.14 1.12 0 .6-.5 1.08-1.14 1.08zm2.1-6.33c-.36.45-.84.74-1.25 1.03-.39.27-.63.53-.63 1.07v.3h-1.4v-.42c0-.86.4-1.38.96-1.78.3-.22.65-.43.91-.74.22-.26.33-.54.33-.87 0-.7-.59-1.16-1.35-1.16-.77 0-1.3.45-1.43 1.2l-1.48-.3c.2-1.34 1.43-2.3 2.95-2.3 1.65 0 2.86 1 2.86 2.44 0 .62-.16 1.14-.47 1.53z"/>
            </svg>
          </div>
          <div class="survey-signal-copy-compact">
            <span class="survey-signal-kicker-compact">Бонус</span>
            <span class="survey-signal-bonus-compact">-{{ survey_reward.amount_uah|default:200 }} грн</span>
          </div>
          <div class="survey-signal-pill-compact">≈5 хв</div>
        </div>

        <!-- Right block -->
        <div class="survey-promo-banner">
          <div class="survey-promo-content">
            <h3 class="survey-promo-title">ВИГРАЙ {{ survey_reward.amount_uah|default:200 }} ГРН ЗА ОПИТУВАННЯ!</h3>
            <p class="survey-promo-subtitle">Дай відповідь на кілька запитань та забери свій промокод!</p>
            
            <div class="survey-promo-actions">
              <button
                type="button"
                class="survey-cta-compact survey-cta"
                data-survey-cta
                data-survey-key="{{ survey_key }}"
                data-survey-start-text="{{ survey_ui_home.cta_start_uk|default:'Пройти опитування' }}"
                data-survey-continue-text="{{ survey_ui_home.cta_continue_uk|default:'Продовжити опитування' }}"
                data-survey-authenticated="{% if request.user.is_authenticated %}1{% else %}0{% endif %}"
                data-login-url="{% url 'login' %}?next={{ request.path }}"
              >
                <span>Пройти опитування</span>
              </button>
              <button type="button" class="survey-dismiss-btn" id="featuredToggle">
                Більше не показувати
              </button>
            </div>
          </div>
          <div class="survey-promo-icon">
            <svg width="84" height="84" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 0 16px rgba(255,140,66,0.5));">
              <path d="M20 7H16C16 5.89543 15.1046 5 14 5C13.1951 5 12.5013 5.47487 12 6.1499C11.4987 5.47487 10.8049 5 10 5C8.89543 5 8 5.89543 8 7H4C3.44772 7 3 7.44772 3 8V11C3 11.5523 3.44772 12 4 12H5V19C5 19.5523 5.44772 20 6 20H18C18.5523 20 19 19.5523 19 19V12H20C20.5523 12 21 11.5523 21 11V8C21 7.44772 20.5523 7 20 7ZM10 6.5C10.2761 6.5 10.5 6.72386 10.5 7C10.5 7.27614 10.2761 7.5 10 7.5C9.72386 7.5 9.5 7.27614 9.5 7C9.5 6.72386 9.72386 6.5 10 6.5ZM14 6.5C14.2761 6.5 14.5 6.72386 14.5 7C14.5 7.27614 14.2761 7.5 14 7.5C13.7238 7.5 13.5 7.27614 13.5 7C13.5 6.72386 13.7238 6.5 14 6.5ZM11 12V18H7V12H11ZM17 18H13V12H17V18ZM19 10.5H5V8.5H19V10.5Z" fill="url(#giftGrad3)" />
              <defs>
                <linearGradient id="giftGrad3" x1="12" y1="5" x2="12" y2="20" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FFD18C" />
                  <stop offset="1" stop-color="#FF8C42" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>

      </div>
    </div>\n"""

# Reconstruct file
new_lines = []
i = 0
while i < len(lines):
    if i == 31: # line 32 (1-based), start of CSS replacement
        new_lines.append(css_replacement)
        while i < 337: # up to 337 (1-based)
            i += 1
        continue
        
    if i == 1266: # line 1267 (1-based), start of HTML replacement
        new_lines.append(html_replacement)
        while i < 1370: # up to 1370 (1-based)
            i += 1
        continue
        
    new_lines.append(lines[i])
    i += 1

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updates applied.")
