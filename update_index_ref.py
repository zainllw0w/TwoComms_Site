import sys

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

css_replacement = """    .survey-card-modern {
      margin: 1.5rem 0;
    }

    .survey-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.25rem;
    }

    .survey-title-main {
      margin: 0;
      color: #fff;
      font-size: clamp(1.4rem, 2.5vw, 1.8rem);
      font-weight: 700;
      letter-spacing: -0.02em;
    }

    .survey-subtitle-main {
      margin: 0.35rem 0 0 0;
      color: rgba(255, 255, 255, 0.7);
      font-size: clamp(0.85rem, 1.5vw, 0.95rem);
    }

    .survey-toggle-pill {
      background: rgba(255, 163, 102, 1);
      color: #1a0c06;
      border: none;
      padding: 0.45rem 1rem;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.8rem;
      cursor: pointer;
      text-transform: uppercase;
      box-shadow: 0 4px 12px rgba(255, 140, 66, 0.25);
      transition: opacity 0.2s;
    }

    .survey-toggle-pill:hover {
      opacity: 0.9;
    }

    .survey-banner-inner {
      background: linear-gradient(135deg, #38160d, #1c0602);
      border-radius: 20px;
      padding: clamp(1.5rem, 3vw, 2.5rem);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255, 140, 66, 0.15);
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }

    .survey-banner-content {
      position: relative;
      z-index: 2;
      max-width: 34rem;
    }

    .survey-banner-title {
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.6rem);
      font-weight: 900;
      line-height: 1.1;
      color: #fff;
      text-transform: uppercase;
      letter-spacing: -0.01em;
    }

    .survey-banner-subtitle {
      margin: 0.85rem 0 0 0;
      color: rgba(255, 255, 255, 0.85);
      font-size: clamp(0.9rem, 1.5vw, 1.05rem);
      line-height: 1.45;
      font-weight: 400;
    }

    .survey-banner-icon {
      position: relative;
      z-index: 1;
    }

    .survey-footer-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 1.25rem;
      flex-wrap: wrap;
      gap: 1.5rem;
    }

    .survey-pills-row {
      display: flex;
      gap: 0.75rem;
      flex-wrap: nowrap;
      overflow-x: auto;
      -ms-overflow-style: none;
      scrollbar-width: none;
      padding-bottom: 0.25rem;
    }
    
    .survey-pills-row::-webkit-scrollbar {
      display: none;
    }

    .survey-pill-item {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.35rem 0.85rem;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      font-size: 0.8rem;
      color: rgba(255, 255, 255, 0.75);
      background: rgba(255, 255, 255, 0.03);
      white-space: nowrap;
    }

    .survey-pill-dot {
      width: 6px;
      height: 6px;
      background: #ffaa55;
      border-radius: 50%;
      box-shadow: 0 0 6px #ffaa55;
    }

    .survey-cta-main {
      background: linear-gradient(135deg, #ff9b55, #ffb347);
      color: #1a0c06;
      border: none;
      padding: 0.85rem 1.75rem;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.95rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 8px 24px rgba(255, 140, 66, 0.3);
      transition: transform 0.2s ease;
      white-space: nowrap;
    }

    .survey-cta-main:hover {
      transform: translateY(-2px);
    }
    
    @media (max-width: 768px) {
      .survey-banner-inner {
        flex-direction: column;
        align-items: flex-start;
        padding: 1.5rem;
        gap: 1.5rem;
      }
      .survey-banner-icon {
        margin-left: auto;
        width: 80px;
        height: 80px;
      }
      .survey-banner-icon svg {
        width: 100%;
        height: 100%;
      }
      .survey-header-row {
        flex-direction: column;
        gap: 1rem;
      }
      .survey-toggle-pill {
        align-self: flex-start;
      }
    }
"""

html_replacement = """    <!-- Скрываемый контент (референсный дизайн) -->
    <div class="featured-content-unified collapsed" id="featured-content" style="display: block; max-height: none; overflow: visible;">
      <div class="survey-card-modern mb-3 mt-2">
        
        <!-- Header row -->
        <div class="survey-header-row">
          <div>
            <h2 class="survey-title-main">Допоможи покращити TWOCOMMS</h2>
            <p class="survey-subtitle-main">Коротке опитування без довгої анкети: відповіді допоможуть нам зробити магазин і колекції кращими.</p>
          </div>
          <button type="button" class="survey-toggle-pill" id="featuredToggle">
            БІЛЬШЕ НЕ ПОКАЗУВАТИ
          </button>
        </div>

        <!-- Banner inner -->
        <div class="survey-banner-inner">
          <div class="survey-banner-content">
            <h3 class="survey-banner-title">
              ВИГРАЙ {{ survey_reward.amount_uah|default:200 }} ГРН<br>ЗА ОПИТУВАННЯ!
            </h3>
            <p class="survey-banner-subtitle">
              Дай відповідь на кілька запитань та забери свій промокод!
            </p>
          </div>
          <div class="survey-banner-icon">
            <svg width="100" height="100" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 0 16px rgba(255,140,66,0.5));">
              <path d="M20 7H16C16 5.89543 15.1046 5 14 5C13.1951 5 12.5013 5.47487 12 6.1499C11.4987 5.47487 10.8049 5 10 5C8.89543 5 8 5.89543 8 7H4C3.44772 7 3 7.44772 3 8V11C3 11.5523 3.44772 12 4 12H5V19C5 19.5523 5.44772 20 6 20H18C18.5523 20 19 19.5523 19 19V12H20C20.5523 12 21 11.5523 21 11V8C21 7.44772 20.5523 7 20 7ZM10 6.5C10.2761 6.5 10.5 6.72386 10.5 7C10.5 7.27614 10.2761 7.5 10 7.5C9.72386 7.5 9.5 7.27614 9.5 7C9.5 6.72386 9.72386 6.5 10 6.5ZM14 6.5C14.2761 6.5 14.5 6.72386 14.5 7C14.5 7.27614 14.2761 7.5 14 7.5C13.7238 7.5 13.5 7.27614 13.5 7C13.5 6.72386 13.7238 6.5 14 6.5ZM11 12V18H7V12H11ZM17 18H13V12H17V18ZM19 10.5H5V8.5H19V10.5Z" fill="url(#giftGrad4)" />
              <defs>
                <linearGradient id="giftGrad4" x1="12" y1="5" x2="12" y2="20" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FFD18C" />
                  <stop offset="1" stop-color="#FF8C42" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>

        <!-- Footer row (Pills + CTA) -->
        <div class="survey-footer-row">
          <div class="survey-pills-row">
            <span class="survey-pill-item"><span class="survey-pill-dot"></span> Без форми на одну сторінку</span>
            <span class="survey-pill-item"><span class="survey-pill-dot"></span> Прогрес збережеться</span>
            <span class="survey-pill-item"><span class="survey-pill-dot"></span> Лише для зареєстрованих користувачів</span>
            <span class="survey-pill-item" style="color: #ffaa55;"><span class="survey-pill-dot"></span> Займе близько 5 хвилин</span>
          </div>
          <button
            type="button"
            class="survey-cta-main"
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
    </div>\n"""

# Reconstruct file
new_lines = []
i = 0
while i < len(lines):
    if i == 31: # line 32 (1-based), start of CSS replacement
        new_lines.append(css_replacement)
        while i < 239: # up to line 239 (1-based), where .survey-modal starts at 240
            i += 1
        continue
        
    if i == 1168: # line 1169 (1-based), start of HTML replacement
        new_lines.append(html_replacement)
        while i < 1226: # up to 1226 (1-based)
            i += 1
        continue
        
    new_lines.append(lines[i])
    i += 1

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updates applied.")
