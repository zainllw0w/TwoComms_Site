import re

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/custom_print.html', 'r' , encoding='utf-8') as f:
    html = f.read()

# 1. Remove is-active from cp-step-mode
html = html.replace('cp-step cp-step--mode is-active', 'cp-step cp-step--mode')

# 2. Wrap in cp-step-viewport
html = html.replace('<div class="cp-waterfall" data-waterfall>', '<div class="cp-waterfall" data-waterfall>\n          <div class="cp-step-viewport" data-step-viewport>')

html = html.replace('''          </section>

        </div>
      </div>
    </form>''', '''          </section>
          </div>
        </div>
      </div>
    </form>''')

# 3. Restructure steps
# We will use regex to find the blocks and reorganize them.
def extract_block(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1: return ""
    end = text.find(end_marker, start)
    if end == -1: return text[start:]
    return text[start:end]

step3 = extract_block(html, '<!-- STEP 3: Config -->', '<!-- STEP 4:')
step4 = extract_block(html, '<!-- STEP 4: Zones + premium addons -->', '<!-- STEP 5:')

# We need to split step3 into Fit and Fabric
# Fit block ends before Fabric block
fit_html = extract_block(step3, '<!-- STEP 3: Config -->', '<div class="cp-config-block" data-fabric-block>')
fabric_html_part = extract_block(step3, '<div class="cp-config-block" data-fabric-block>', '<div class="cp-config-block" data-addons-wrap hidden>')
addons_html = extract_block(step3, '<div class="cp-config-block" data-addons-wrap hidden>', '<div class="cp-step-actions">')
actions3 = extract_block(step3, '<div class="cp-step-actions">', '</section>') + '</section>\n\n'

# Fabric block ends at addons
fabric_block = fabric_html_part

# Now reassemble the new steps:
new_step3_fit = fit_html.replace('data-step="config"', 'data-step="fit"').replace('id="cp-step-config"', 'id="cp-step-fit"')
new_step3_fit = new_step3_fit.replace('3. Налаштування', '3. Крій / Силует').replace('Налаштування', 'Крій')
new_step3_fit = new_step3_fit.replace('Крій, тканина, колір', 'Крій та посадка')
# Change navigation in step 3
new_step3_fit += '''              <div class="cp-step-actions">
                <button type="button" class="cp-secondary-button" data-step-back="product">Назад</button>
                <button type="button" class="cp-link cp-link--primary" data-step-next="fabric">Далі до тканини</button>
              </div>
            </div>
          </section>

'''

new_step4_fabric = '''          <!-- STEP 4: Fabric + Color -->
          <section class="cp-step is-pending" data-step="fabric" id="cp-step-fabric">
            <div class="cp-step-summary" data-step-summary-row>
              <span class="cp-step-summary-num">4</span>
              <div class="cp-step-summary-text">
                <small>Тканина і колір</small>
                <strong data-step-summary-value="fabric">—</strong>
              </div>
              <button type="button" class="cp-step-summary-edit" data-step-edit="fabric">Змінити</button>
            </div>
            <div class="cp-step-body">
              <div class="cp-step-head">
                <span class="cp-card-eyebrow">4. Тканина і колір</span>
                <h2>Вибір тканини і кольору</h2>
                <p>Оберіть тканину та колір вашого виробу.</p>
              </div>
''' + fabric_block + '''              <div class="cp-step-actions">
                <button type="button" class="cp-secondary-button" data-step-back="fit">Назад</button>
                <button type="button" class="cp-link cp-link--primary" data-step-next="zones">Далі до зон</button>
              </div>
            </div>
          </section>

'''

new_step5_zones = step4.replace('<!-- STEP 4: Zones', '<!-- STEP 5: Zones').replace('<span class="cp-step-summary-num">4</span>', '<span class="cp-step-summary-num">5</span>').replace('4. Зони друку', '5. Зони друку та деталі')
# Add addons to zones
new_step5_zones = new_step5_zones.replace('<div class="cp-step-actions">', addons_html + '\n              <div class="cp-step-actions">')
new_step5_zones = new_step5_zones.replace('data-step-back="config"', 'data-step-back="fabric"')

# Replace old steps with new steps in HTML
final_html = html.replace(step3 + step4, new_step3_fit + new_step4_fabric + new_step5_zones)

# Update step counters for remaining steps
final_html = final_html.replace('<!-- STEP 5:', '<!-- STEP 6:')
final_html = final_html.replace('<span class="cp-step-summary-num">5</span>', '<span class="cp-step-summary-num">6</span>')
final_html = final_html.replace('5. Макет', '6. Макет')

final_html = final_html.replace('<!-- STEP 6:', '<!-- STEP 7:')
final_html = final_html.replace('<span class="cp-step-summary-num">6</span>', '<span class="cp-step-summary-num">7</span>')
final_html = final_html.replace('6. Кількість і розміри', '7. Кількість і розміри')

final_html = final_html.replace('<!-- STEP 7:', '<!-- STEP 8:')
final_html = final_html.replace('<span class="cp-step-summary-num">7</span>', '<span class="cp-step-summary-num">8</span>')
final_html = final_html.replace('7. Подарунок', '8. Подарунок')

final_html = final_html.replace('<!-- STEP 8:', '<!-- STEP 9:')
final_html = final_html.replace('<span class="cp-step-summary-num">8</span>', '<span class="cp-step-summary-num">9</span>')
final_html = final_html.replace('8. Контакт і фінал', '9. Контакт і фінал')

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/custom_print.html', 'w', encoding='utf-8') as f:
    f.write(final_html)

print("Done HTML restructure")
