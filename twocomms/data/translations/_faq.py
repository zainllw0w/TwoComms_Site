"""Hand-curated RU/EN translations for FAQ questions and their answers."""
from __future__ import annotations

# Lookup is by Ukrainian question text. The same UA question may appear under
# many products on prod — the importer applies the matching RU/EN to all rows.
# Some answers vary slightly between products (e.g. "ця футболка" vs "ця худі"),
# but they were already templated by category. We translate every observed
# UA answer separately via the ``ANSWERS`` map.

QUESTIONS: dict[str, dict[str, str]] = {
    "Де розміщений принт?": {
        "ru": "Где расположен принт?",
        "en": "Where is the print located?",
    },
    "З чим носити цю футболку?": {
        "ru": "С чем носить эту футболку?",
        "en": "What can I wear this tee with?",
    },
    "Кому пасує принт «Довіряй Своїй Божевільній Ідеї»?": {
        "ru": "Кому подойдёт принт «Доверяй Своей Безумной Идее»?",
        "en": "Who is the “Trust Your Crazy Idea” print for?",
    },
    "У чому відмінність «Харків Edition» від «Харківської Області»?": {
        "ru": "В чём отличие «Харьков Edition» от «Харьковской Области»?",
        "en": "What is the difference between “Kharkiv Edition” and “Kharkiv Region”?",
    },
    "У якому стилі виконано принт «Silent Winter»?": {
        "ru": "В каком стиле выполнен принт «Silent Winter»?",
        "en": "What style is the “Silent Winter” print in?",
    },
    "У якому стилі виконано принт «Печатка Хулігана»?": {
        "ru": "В каком стиле выполнен принт «Печать Хулигана»?",
        "en": "What style is the “Hooligan's Stamp” print in?",
    },
    "Це універсальна модель «Харківська Область»?": {
        "ru": "Это универсальная модель «Харьковская Область»?",
        "en": "Is “Kharkiv Region” a universal model?",
    },
    "Це чоловіча чи жіноча футболка?": {
        "ru": "Это мужская или женская футболка?",
        "en": "Is this a men's or a women's tee?",
    },
    "Чи доступна ця лонгслів без принту?": {
        "ru": "Доступен ли этот лонгслив без принта?",
        "en": "Is this longsleeve available without the print?",
    },
    "Чи доступна ця футболка без принту?": {
        "ru": "Доступна ли эта футболка без принта?",
        "en": "Is this tee available without the print?",
    },
    "Чи доступна ця худі без принту?": {
        "ru": "Доступна ли эта худи без принта?",
        "en": "Is this hoodie available without the print?",
    },
    "Чи можна замовити лонгслів зі своїм принтом?": {
        "ru": "Можно ли заказать лонгслив со своим принтом?",
        "en": "Can I order this longsleeve with my own print?",
    },
    "Чи можна замовити футболку зі своїм принтом?": {
        "ru": "Можно ли заказать футболку со своим принтом?",
        "en": "Can I order this tee with my own print?",
    },
    "Чи можна замовити худі зі своїм принтом?": {
        "ru": "Можно ли заказать худи со своим принтом?",
        "en": "Can I order this hoodie with my own print?",
    },
    "Чи це святковий/новорічний принт?": {
        "ru": "Это праздничный/новогодний принт?",
        "en": "Is this a holiday / Christmas print?",
    },
    "Чи частина грошей з цього футболки йде на підтримку 225 ОШП?": {
        "ru": "Идёт ли часть денег с этой футболки на поддержку 225 ОШБр?",
        "en": "Does part of this tee's price support the 225th Assault Brigade?",
    },
    "Чи частина грошей з цього худі йде на підтримку 225 ОШП?": {
        "ru": "Идёт ли часть денег с этой худи на поддержку 225 ОШБр?",
        "en": "Does part of this hoodie's price support the 225th Assault Brigade?",
    },
    "Чи є особливий сенс у принті «Red Leaves»?": {
        "ru": "Есть ли особый смысл у принта «Red Leaves»?",
        "en": "Does the “Red Leaves” print carry a deeper meaning?",
    },
    "Чим Dark Neon відрізняється від рожевої версії?": {
        "ru": "Чем Dark Neon отличается от розовой версии?",
        "en": "How does Dark Neon differ from the pink version?",
    },
    "Чим V2.0 відрізняється від першої версії?": {
        "ru": "Чем V2.0 отличается от первой версии?",
        "en": "What's different in V2.0 versus the first edition?",
    },
    "Чому «Ментол»?": {
        "ru": "Почему «Ментол»?",
        "en": "Why “Mint”?",
    },
    "Чому принт «Glory of Ukraine» англійською?": {
        "ru": "Почему принт «Glory of Ukraine» на английском?",
        "en": "Why is the “Glory of Ukraine” print in English?",
    },
    "Чому саме Покровськ?": {
        "ru": "Почему именно Покровск?",
        "en": "Why Pokrovsk specifically?",
    },
    "Чому ця модель «Limited Edition»?": {
        "ru": "Почему эта модель «Limited Edition»?",
        "en": "Why is this model “Limited Edition”?",
    },
    "Що мається на увазі під «Стиль — Це Все»?": {
        "ru": "Что подразумевается под «Стиль — Это Всё»?",
        "en": "What does “Style Is Everything” mean?",
    },
    "Що означає «Reality Bends: Future 2026»?": {
        "ru": "Что означает «Reality Bends: Future 2026»?",
        "en": "What does “Reality Bends: Future 2026” mean?",
    },
    "Що означає «Життя Бентежне»?": {
        "ru": "Что означает «Жизнь Тревожная»?",
        "en": "What does “Life Is Restless” mean?",
    },
    "Що означає «мені поЖуй — це філософія»?": {
        "ru": "Что означает «мне поЖуй — это философия»?",
        "en": "What does “I don't give a damn — it's a philosophy” mean?",
    },
    "Що означає напис «Тильний В Єб*Ло»?": {
        "ru": "Что означает надпись «Тыльный В Еб*Ло»?",
        "en": "What does the phrase “Stockless Punch” mean?",
    },
    "Що означає принт «My Little Baby»?": {
        "ru": "Что означает принт «My Little Baby»?",
        "en": "What does the “My Little Baby” print mean?",
    },
    "Що означає принт «death grabs ass»?": {
        "ru": "Что означает принт «death grabs ass»?",
        "en": "What does the “death grabs ass” print mean?",
    },
    "Що означає принт «Бізнес — Це Математика»?": {
        "ru": "Что означает принт «Бизнес — Это Математика»?",
        "en": "What does the “Business Is Math” print mean?",
    },
    "Що означає принт «Довіряй своїй божевільній ідеї»?": {
        "ru": "Что означает принт «Доверяй своей безумной идее»?",
        "en": "What does the “Trust Your Crazy Idea” print mean?",
    },
    "Що означає принт «Дрони навколо 2.0»?": {
        "ru": "Что означает принт «Дроны Вокруг 2.0»?",
        "en": "What does the “Drones Around 2.0” print mean?",
    },
    "Що означає принт «Річ Йде Про Двозначні Суми»?": {
        "ru": "Что означает принт «Речь Идёт О Двузначных Суммах»?",
        "en": "What does the “Talking Double-Digit Sums” print mean?",
    },
    "Що означає фраза «І На Той Світ З Собою Візьму»?": {
        "ru": "Что означает фраза «И На Тот Свет С Собой Заберу»?",
        "en": "What does the phrase “I'll Take You With Me To The Other Side” mean?",
    },
    "Що це за гра слів — «Lord Of The Lending»?": {
        "ru": "Что за игра слов — «Lord Of The Lending»?",
        "en": "What's the wordplay behind “Lord Of The Lending”?",
    },
    "Як довго їде доставка?": {
        "ru": "Сколько идёт доставка?",
        "en": "How long does shipping take?",
    },
    "Як обрати розмір лонгсліва?": {
        "ru": "Как выбрать размер лонгслива?",
        "en": "How do I pick the right longsleeve size?",
    },
    "Як обрати розмір футболки?": {
        "ru": "Как выбрать размер футболки?",
        "en": "How do I pick the right tee size?",
    },
    "Як обрати розмір худі?": {
        "ru": "Как выбрать размер худи?",
        "en": "How do I pick the right hoodie size?",
    },
    "Як прати лонгслів, щоб принт залишився яскравим?": {
        "ru": "Как стирать лонгслив, чтобы принт оставался ярким?",
        "en": "How should I wash the longsleeve to keep the print bright?",
    },
    "Як прати футболку, щоб принт не зіпсувався?": {
        "ru": "Как стирать футболку, чтобы принт не испортился?",
        "en": "How should I wash the tee so the print stays intact?",
    },
    "Як прати худі, щоб не зіпсувалося?": {
        "ru": "Как стирать худи, чтобы не испортилось?",
        "en": "How should I wash the hoodie so it stays in shape?",
    },
    "Як швидко доставимо футболку?": {
        "ru": "Как быстро доставим футболку?",
        "en": "How fast will the tee arrive?",
    },
    "Як швидко доставимо худі?": {
        "ru": "Как быстро доставим худи?",
        "en": "How fast will the hoodie arrive?",
    },
    "Який сенс у принті «last breath»?": {
        "ru": "В чём смысл принта «last breath»?",
        "en": "What's the meaning behind the “last breath” print?",
    },
}


ANSWERS: dict[str, dict[str, str]] = {
    "Основний авторський принт розміщений на спині. Саме він є головним візуальним акцентом футболки.": {
        "ru": "Основной авторский принт расположен на спине — именно он становится главным визуальным акцентом футболки.",
        "en": "The main author print sits on the back — that's where the tee's key visual statement lives.",
    },
    "Вона добре поєднується з карго, джинсами, чорними або хакі штанами, шортами, сорочкою, худі, кросівками або берцями.": {
        "ru": "Хорошо сочетается с карго, джинсами, чёрными или хаки-штанами, шортами, рубашкой, худи, кроссовками или берцами.",
        "en": "It pairs well with cargos, jeans, black or khaki pants, shorts, a shirt, a hoodie, sneakers or combat boots.",
    },
    "Творцям, підприємцям, художникам, авторам — усім, хто знає, що означає вірити у задум, коли ще ніхто навколо не вірить. Streetwear-амулет для тих, хто будує своє.": {
        "ru": "Создателям, предпринимателям, художникам, авторам — всем, кто знает, каково верить в идею, когда вокруг ещё никто не верит. Streetwear-амулет для тех, кто строит своё.",
        "en": "For creators, founders, artists and authors — anyone who knows what it's like to believe in an idea before anyone else does. A streetwear amulet for people building their own thing.",
    },
    "«Харків Edition» — стилізована streetwear-версія з акцентом на сучасні шрифти та локальну ідентичність. «Харківська Область» — лаконічна версія для мінімалістів. Обидві про любов до Слобожанщини.": {
        "ru": "«Харьков Edition» — стилизованная streetwear-версия с акцентом на современные шрифты и локальную идентичность. «Харьковская Область» — лаконичная версия для минималистов. Обе — о любви к Слобожанщине.",
        "en": "“Kharkiv Edition” is a stylised streetwear take with modern type and local identity. “Kharkiv Region” is a minimalist counterpart. Both express love for the Slobozhanshchyna region.",
    },
    "Атмосферна зимова графіка у спокійній темній палітрі — без агресії, без яскравих акцентів. Принт у дусі тихої краси холодного сезону.": {
        "ru": "Атмосферная зимняя графика в спокойной тёмной палитре — без агрессии, без ярких акцентов. Принт в духе тихой красоты холодного сезона.",
        "en": "An atmospheric winter graphic in a calm dark palette — no aggression, no loud accents. A print built around the quiet beauty of the cold season.",
    },
    "Панково-вулична естетика: трохи неохайна графіка, різкі лінії, характерний 90-х шрифт. Принт TwoComms для тих, хто цінує streetwear без глянцю.": {
        "ru": "Панково-уличная эстетика: слегка небрежная графика, резкие линии, характерный шрифт 90-х. Принт TwoComms для тех, кто ценит streetwear без глянца.",
        "en": "A punk-street aesthetic: slightly rough graphics, sharp lines, that classic '90s typeface. A TwoComms print for those who like streetwear without gloss.",
    },
    "Так — принт лаконічний, без офіційної геральдики. Підходить і для повсякденного носіння у місті, і для поїздок. Пасує до streetwear, casual та semi-formal комплектів.": {
        "ru": "Да — принт лаконичный, без официальной геральдики. Подходит и для повседневной носки в городе, и для поездок. Сочетается со streetwear, casual и semi-formal комплектами.",
        "en": "Yes — the print is minimal, no official heraldry. Works for daily city wear and travel alike, and pairs with streetwear, casual or semi-formal outfits.",
    },
    "Це футболка унісекс. Вона підходить і чоловікам, і жінкам завдяки універсальній посадці та чорній базі.": {
        "ru": "Это футболка унисекс. Подходит и мужчинам, и женщинам благодаря универсальной посадке и чёрной базе.",
        "en": "It's a unisex tee — fits both men and women thanks to a universal cut and a black base.",
    },
    "Так — це базова класична модель TwoComms без принту. Однотонний матеріал у нейтральних кольорах, ідеальна як основа streetwear-гардероба або як база під шарування з іншими речами TwoComms.": {
        "ru": "Да — это базовая классическая модель TwoComms без принта. Однотонный материал в нейтральных цветах, идеальна как основа streetwear-гардероба или как база под лайеринг с другими вещами TwoComms.",
        "en": "Yes — this is the print-free TwoComms classic. A solid neutral fabric, perfect as a streetwear-wardrobe base or for layering with other TwoComms pieces.",
    },
    "Так — у TwoComms є сервіс кастомного друку. Надішліть макет, оберіть колір і розмір лонгсліва — ми надрукуємо й доставимо.": {
        "ru": "Да — у TwoComms есть сервис кастомной печати. Пришлите макет, выберите цвет и размер лонгслива — мы напечатаем и доставим.",
        "en": "Yes — TwoComms offers custom printing. Send us the artwork, pick the longsleeve colour and size, and we'll print and ship it.",
    },
    "Так — у TwoComms є сервіс кастомного друку. Надішліть макет, оберіть колір і розмір, ми надрукуємо й доставимо. Мінімальне замовлення — 1 одиниця.": {
        "ru": "Да — у TwoComms есть сервис кастомной печати. Пришлите макет, выберите цвет и размер — мы напечатаем и доставим. Минимальный заказ — 1 единица.",
        "en": "Yes — TwoComms runs a custom-print service. Send the artwork, choose colour and size, we print and ship. Minimum order: 1 piece.",
    },
    "Так — оформіть кастомний друк через нашу форму: завантажте макет, оберіть колір і розмір базового худі, ми надрукуємо й доставимо персональну модель.": {
        "ru": "Да — оформите кастомную печать через нашу форму: загрузите макет, выберите цвет и размер базовой худи, мы напечатаем и доставим персональную модель.",
        "en": "Yes — order a custom print through our form: upload the artwork, pick the base hoodie colour and size, and we'll deliver your personal piece.",
    },
    "Так — це авторський різдвяний принт TwoComms у дусі чорного гумору. Не «солодке Різдво», а провокаційний жарт. Підходить як головний акцент святкового образу або як іронічний подарунок.": {
        "ru": "Да — это авторский рождественский принт TwoComms в духе чёрного юмора. Не «сладкое Рождество», а провокационная шутка. Подходит как главный акцент праздничного образа или как ироничный подарок.",
        "en": "Yes — it's an author-driven TwoComms Christmas print built on dark humor. Not a sugary holiday card, but a provocative joke. Great as the centerpiece of a festive look or an ironic gift.",
    },
    "Так — це спеціальна серія TwoComms на підтримку 225-го окремого штурмового полку «Команда Сірко». Частина прибутку йде безпосередньо на потреби підрозділу.": {
        "ru": "Да — это специальная серия TwoComms в поддержку 225-го отдельного штурмового полка «Команда Сирко». Часть прибыли идёт напрямую на нужды подразделения.",
        "en": "Yes — this is a TwoComms special edition supporting the 225th Separate Assault Regiment “Team Sirko”. A share of the profit goes directly to the unit.",
    },
    "Цей принт — суто естетичний: червоне листя як акцент осінньої гами без іронії та політичних меседжів. Просто тонка авторська ілюстрація для тих, хто любить тиху красу.": {
        "ru": "Этот принт — чисто эстетический: красные листья как акцент осенней гаммы, без иронии и политических смыслов. Просто тонкая авторская иллюстрация для тех, кто любит тихую красоту.",
        "en": "The print is purely aesthetic: red leaves as an autumn accent, no irony or political subtext. Just a delicate author illustration for those who love quiet beauty.",
    },
    "Dark Neon Edition — темна (чорна база) редакція тієї самої колекції «Reality Bends: Future 2026» з неоновими акцентами. Агресивніша, драматичніша, для тих, хто обирає темну естетику. Принт той самий, характер інший.": {
        "ru": "Dark Neon Edition — тёмная (чёрная база) редакция той же коллекции «Reality Bends: Future 2026» с неоновыми акцентами. Агрессивнее, драматичнее, для тех, кто выбирает тёмную эстетику. Принт тот же, характер другой.",
        "en": "Dark Neon Edition is the black-base release of the same “Reality Bends: Future 2026” collection, accented with neon. More aggressive, more dramatic — for those who choose the dark aesthetic. Same print, different character.",
    },
    "Друга версія принту «Покровськ» має перероблену графіку: чіткіші лінії, оновлену палітру, додані стилістичні акценти. Меседж той самий — пам'ять про дім.": {
        "ru": "Вторая версия принта «Покровск» получила переработанную графику: более чёткие линии, обновлённую палитру, новые стилистические акценты. Сообщение прежнее — память о доме.",
        "en": "The second “Pokrovsk” edition features reworked graphics: cleaner lines, an updated palette, fresh stylistic accents. Same message — memory of home.",
    },
    "Ментолова — пастельна версія колекції «Reality Bends: Future 2026». База у м'якому ментоловому відтінку, неонові деталі принту. Легший, атмосферніший варіант тієї самої флагманської серії. Ідеально для літніх комплектів.": {
        "ru": "Ментоловая — пастельная версия коллекции «Reality Bends: Future 2026». База в мягком ментоловом оттенке, неоновые детали принта. Более лёгкий и атмосферный вариант той же флагманской серии. Идеально для летних комплектов.",
        "en": "Mint is the pastel release of the “Reality Bends: Future 2026” collection. A soft mint base with neon print details. A lighter, more atmospheric take on the same flagship series — perfect for summer outfits.",
    },
    "Англомовний меседж розрахований на міжнародну аудиторію: іноземних знайомих, гостей з-за кордону, контекст за межами України. Принт зрозумілий без перекладу — і саме в цьому його сила.": {
        "ru": "Англоязычное послание рассчитано на международную аудиторию: иностранных знакомых, гостей из-за рубежа, контекст за пределами Украины. Принт понятен без перевода — и в этом его сила.",
        "en": "The English-language message is built for an international audience: foreign friends, guests from abroad, contexts beyond Ukraine. The print reads without translation — and that's its strength.",
    },
    "Покровськ — місто Донецької області, ім'я якого зараз лунає у новинах. Принт TwoComms — поетична присвята жінкам, які лишили східні міста, але не лишили їх у своєму серці.": {
        "ru": "Покровск — город Донецкой области, имя которого сейчас звучит в новостях. Принт TwoComms — поэтическое посвящение женщинам, покинувшим восточные города, но сохранившим их в сердце.",
        "en": "Pokrovsk is a city in Donetsk region whose name is in the news now. The TwoComms print is a poetic tribute to the women who left the eastern cities but never left them behind in their hearts.",
    },
    "Це справді лімітована партія: обмежений тираж, фірмова поліграфія всередині комірця, нумерована серія. Після розпродажу нова партія не виходитиме.": {
        "ru": "Это действительно лимитированная партия: ограниченный тираж, фирменная полиграфия внутри ворота, нумерованная серия. После распродажи новая партия не выйдет.",
        "en": "It really is a limited run: short production volume, signature inside-collar print, numbered series. Once it sells out, there'll be no re-release.",
    },
    "Це маніфест: стиль як остання опора, коли довкола падає все. Не модний прокат, а спосіб тримати характер. Принт TwoComms про віру в форму.": {
        "ru": "Это манифест: стиль как последняя опора, когда вокруг рушится всё. Не модный прокат, а способ удержать характер. Принт TwoComms о вере в форму.",
        "en": "It's a manifesto: style as the last pillar when everything else is falling apart. Not a fashion rental, but a way to hold your character. A TwoComms print about faith in form.",
    },
    "Це флагманська колекція TwoComms сезону 2026 у дусі cyberpunk-естетики: реальність, що гнеться, неонові відблиски, відчуття близького майбутнього. Рожеве виконання — основний колір серії, є ще Dark Neon та Ментол-версії.": {
        "ru": "Это флагманская коллекция TwoComms сезона 2026 в духе cyberpunk-эстетики: реальность, которая гнётся, неоновые отблески, ощущение близкого будущего. Розовое исполнение — основной цвет серии, есть также Dark Neon и Ментол-версии.",
        "en": "It's TwoComms' flagship 2026 collection in cyberpunk-inspired aesthetics: bending reality, neon glimmers, the feeling of a near future. The pink edition is the core colour of the series, with Dark Neon and Mint variants alongside.",
    },
    "Це ліричний рядок про красу неспокою — те живе хвилювання, що тримає людину пробудженою. Принт TwoComms у дусі тихої поезії.": {
        "ru": "Это лирическая строка о красоте беспокойства — том живом волнении, которое удерживает человека пробуждённым. Принт TwoComms в духе тихой поэзии.",
        "en": "A lyrical line about the beauty of restlessness — the living tension that keeps a person awake. A TwoComms print in the spirit of quiet poetry.",
    },
    "Це streetwear-афоризм про здорову байдужість до зайвого: не цинізм, а спокійне розставлення пріоритетів. Принт-маніфест TwoComms для тих, хто живе своїм без оглядання на чужі очікування.": {
        "ru": "Это streetwear-афоризм о здоровом безразличии к лишнему: не цинизм, а спокойная расстановка приоритетов. Принт-манифест TwoComms для тех, кто живёт своим, не оглядываясь на чужие ожидания.",
        "en": "A streetwear aphorism about healthy detachment from the unnecessary: not cynicism, but calm priority-setting. A TwoComms manifesto print for those who live by their own rules and stop chasing others' expectations.",
    },
    "Це військовий сленг — пряма цитата з армійської мови, без цензури й пафосу. Принт у дусі streetwear-маніфесту: для тих, хто знає, що означає служба, і не боїться прямої мови.": {
        "ru": "Это военный сленг — прямая цитата из армейского языка, без цензуры и пафоса. Принт в духе streetwear-манифеста: для тех, кто знает, что такое служба, и не боится прямого языка.",
        "en": "It's army slang — a direct quote from military speech, no censorship or grandstanding. A streetwear manifesto print: for those who know what service is and aren't afraid of blunt language.",
    },
    "Це авторський принт TwoComms у дусі контрасту: ніжна графіка на щільному streetwear-силуеті. Жарт, упізнаваний тими, хто цінує іронію без переходу в кітч. Нанесено DTF-друком — насичено, тонко, стійко до прання.": {
        "ru": "Это авторский принт TwoComms в духе контраста: нежная графика на плотном streetwear-силуэте. Шутка, узнаваемая теми, кто ценит иронию без перехода в китч. Нанесён DTF-печатью — насыщенно, тонко, стойко к стирке.",
        "en": "An author-driven TwoComms print built on contrast: a tender graphic on a dense streetwear silhouette. A joke for those who appreciate irony without sliding into kitsch. DTF-printed — saturated, precise and wash-resistant.",
    },
    "Це англомовний мем-принт у дусі streetwear-абсурду: чорний гумор без пафосу та політичного підтексту. Образ для тих, хто цінує іронію та не боїться провокаційних написів.": {
        "ru": "Это англоязычный мем-принт в духе streetwear-абсурда: чёрный юмор без пафоса и политического подтекста. Образ для тех, кто ценит иронию и не боится провокационных надписей.",
        "en": "An English-language meme print in the streetwear-absurd vein: dark humor with no pathos or political subtext. For those who value irony and aren't afraid of provocative slogans.",
    },
    "Це іронічний streetwear-принт про правду підприємництва: холодна арифметика замість мотиваційних плакатів. Принт розпізнають ті, хто будував щось своє.": {
        "ru": "Это ироничный streetwear-принт о правде предпринимательства: холодная арифметика вместо мотивационных постеров. Принт узнают те, кто строил что-то своё.",
        "en": "An ironic streetwear print about the truth of entrepreneurship: cold arithmetic instead of motivational posters. Built to be recognized by anyone who's launched something of their own.",
    },
    "Це принт про віру у власний шлях, навіть якщо ідея здається занадто сміливою або незрозумілою для інших. У філософії TwoComms це код продовження, характеру й внутрішньої свободи.": {
        "ru": "Это принт о вере в свой путь, даже если идея кажется слишком смелой или непонятной для других. В философии TwoComms — это код продолжения, характера и внутренней свободы.",
        "en": "A print about believing in your own path, even when the idea feels too bold or unreadable to others. In the TwoComms philosophy it's a code of persistence, character and inner freedom.",
    },
    "Це оновлена редакція мілітарного принту TwoComms про реальність повітряних загроз — звуки, силуети, напруження. Графіка переосмислена для другої версії: чіткіші лінії, акцентні кольори, сильний меседж.": {
        "ru": "Это обновлённая редакция военного принта TwoComms о реальности воздушных угроз — звуки, силуэты, напряжение. Графика переосмыслена для второй версии: более чёткие линии, акцентные цвета, сильное послание.",
        "en": "The updated edition of TwoComms' military print about the reality of aerial threats — sounds, silhouettes, tension. The graphic was rebuilt for V2: cleaner lines, accent colours, a stronger message.",
    },
    "Іронічна фраза про моменти, коли розмова переходить у серйозну площину — фріланс, перемовини, бізнес-ставки. Принт-кодовий знак для тих, хто розуміє правду грошових діалогів.": {
        "ru": "Ироничная фраза о моментах, когда разговор переходит в серьёзную плоскость — фриланс, переговоры, бизнес-ставки. Принт-кодовый знак для тех, кто понимает правду денежных диалогов.",
        "en": "An ironic line for the moment a conversation tilts into something serious — freelance, negotiations, business stakes. A coded print for those fluent in the truth of money talk.",
    },
    "Це поетичний рядок про любов і вірність — обіцянка забрати кохану людину куди завгодно, навіть за межі життя. Темний романтичний меседж без пафосу.": {
        "ru": "Это поэтическая строка о любви и верности — обещание забрать любимого человека куда угодно, даже за пределы жизни. Тёмное романтическое послание без пафоса.",
        "en": "A poetic line about love and devotion — a promise to take your loved one anywhere, even beyond life. A dark romantic message without melodrama.",
    },
    "Сатирична пародія на «Lord of the Rings»: принт про королів кредитного відділу, які володіють вашою розстрочкою. Англомовний streetwear-гумор для тих, хто сміється з фінансової системи.": {
        "ru": "Сатирическая пародия на «Lord of the Rings»: принт о королях кредитного отдела, которые владеют вашей рассрочкой. Англоязычный streetwear-юмор для тех, кто смеётся над финансовой системой.",
        "en": "A satirical riff on “Lord of the Rings”: a print about the lords of the lending department who own your payment plan. English-language streetwear humor for anyone who laughs at the financial system.",
    },
    "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська від 180 ₴. Оформлюйте до 14:00 — відправимо сьогодні.": {
        "ru": "Новой Почтой — 1–3 рабочих дня. Отделение/почтомат от 85 ₴, адресная курьерская от 180 ₴. Оформляйте до 14:00 — отправим сегодня.",
        "en": "Nova Poshta delivery takes 1–3 business days. Branch/parcel locker from 85 UAH, courier-to-door from 180 UAH. Order by 2 PM and we ship the same day.",
    },
    "Для класичного (regular) силуету — свій звичний розмір; для oversize — на 1 більший. Якщо плануєте шарувати лонгслів під худі або куртку, беріть свій звичний розмір.": {
        "ru": "Для классического (regular) силуэта — ваш привычный размер; для oversize — на 1 больше. Если планируете лайеринг под худи или куртку, берите привычный размер.",
        "en": "For a regular fit, pick your usual size; for oversize, go one up. If you plan to layer the longsleeve under a hoodie or jacket, stick to your usual size.",
    },
    "Орієнтуйтеся на розмірну сітку. Для regular fit — свій звичний розмір; для oversize — на 1 менший (помірний оверсайз) або свій (виразний). У сумнівах між двома — беріть більший.": {
        "ru": "Ориентируйтесь на размерную сетку. Для regular fit — ваш привычный размер; для oversize — на 1 меньше (умеренный оверсайз) или ваш (выразительный). В сомнениях между двумя — берите больший.",
        "en": "Use the size chart. For regular fit, pick your usual size; for oversize, go one down (moderate oversize) or your usual (pronounced). When in doubt between two sizes — go up.",
    },
    "Для класичного силуету — свій звичний розмір; для oversize — на 1 більший. Якщо плануєте шарувати худі поверх сорочки/лонгсліва, рекомендуємо взяти на розмір більший за звичний.": {
        "ru": "Для классического силуэта — ваш привычный размер; для oversize — на 1 больше. Если планируете носить худи поверх рубашки/лонгслива, рекомендуем брать на размер больше привычного.",
        "en": "For a classic fit, pick your usual size; for oversize, go one up. If you plan to layer the hoodie over a shirt or longsleeve, take one size up from your usual.",
    },
    "Прання при 30 °C, навиворіт, без відбілювачів. Сушити природним способом. Прасування лише з вивороту або через тканину, не торкаючись праскою принта.": {
        "ru": "Стирка при 30 °C, наизнанку, без отбеливателей. Сушить естественным способом. Гладить только с изнанки или через ткань, не касаясь утюгом принта.",
        "en": "Wash at 30 °C, inside out, no bleach. Air-dry only. Iron from the inside or through a cloth — never touch the print with the iron.",
    },
    "Виверніть навиворіт, прийте при 30 °C у режимі для бавовни без відбілювачів. Сушіть на повітрі. Прасувати можна з вивороту або через марлю. DTF-принт витримує 50+ циклів такого прання.": {
        "ru": "Выверните наизнанку, стирайте при 30 °C в режиме для хлопка без отбеливателей. Сушите на воздухе. Гладить можно с изнанки или через марлю. DTF-принт выдерживает 50+ циклов такой стирки.",
        "en": "Turn inside out, wash at 30 °C on a cotton cycle without bleach. Air-dry only. Iron inside out or through cheesecloth. The DTF print easily survives 50+ wash cycles.",
    },
    "Прання при 30 °C, режим для бавовни, навиворіт, без відбілювачів. Сушити горизонтально або на плічках — не на батареї та не в сушарці. Прасування лише з вивороту, не торкайтеся праскою принта.": {
        "ru": "Стирка при 30 °C, режим для хлопка, наизнанку, без отбеливателей. Сушить горизонтально или на плечиках — не на батарее и не в сушилке. Гладить только с изнанки, не касаясь утюгом принта.",
        "en": "Wash at 30 °C on a cotton cycle, inside out, without bleach. Dry flat or on a hanger — never on a radiator or in a tumble dryer. Iron inside out and never touch the print.",
    },
    "Новою Поштою — 1–3 робочі дні по всій Україні. Відділення/поштомат від 85 ₴, кур'єр від 180 ₴. Замовлення до 14:00 відправляємо того ж дня.": {
        "ru": "Новой Почтой — 1–3 рабочих дня по всей Украине. Отделение/почтомат от 85 ₴, курьер от 180 ₴. Заказы до 14:00 отправляем в тот же день.",
        "en": "Nova Poshta covers all of Ukraine in 1–3 business days. Branch/parcel locker from 85 UAH, courier from 180 UAH. Orders placed before 2 PM ship the same day.",
    },
    "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська доставка від 180 ₴. Замовлення до 14:00 йдуть того ж дня.": {
        "ru": "Новой Почтой — 1–3 рабочих дня. Отделение/почтомат от 85 ₴, адресная курьерская доставка от 180 ₴. Заказы до 14:00 уходят в тот же день.",
        "en": "Nova Poshta — 1–3 business days. Branch/parcel locker from 85 UAH, courier-to-door from 180 UAH. Orders placed before 2 PM ship the same day.",
    },
    "Це принт про межу — момент перед рішучою дією. Мінімалістична графіка для тих, хто живе у режимі високих ставок. Без декоративності — тільки суть.": {
        "ru": "Это принт о пределе — моменте перед решающим действием. Минималистичная графика для тех, кто живёт в режиме высоких ставок. Без декоративности — только суть.",
        "en": "A print about the edge — the moment before a decisive move. Minimalist graphics for people living in a high-stakes mode. No decoration — only essence.",
    },
}
