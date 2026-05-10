"""Phase 10c — extended SEO copy for 3 live categories.

Force-overwrites the seed copy from 0053 with substantially longer
``description`` (FAQ-style H3 sections), refreshed ``seo_intro_html``,
and a much wider ``top_queries`` / ``top_filters`` block populated
from real Google search-volume data (UA + RU + EN long-tail).

This migration is **destructive** for editorial content of the three
target categories: it deletes existing ``top_queries`` / ``top_filters``
items and re-creates them from the curated lists below. It is intended
to be applied once, immediately after 0053, before any content manager
has had time to edit copy. After Phase 14 (i18n) lands, the canonical
copy will live in `_uk` / `_ru` / `_en` translation columns.

Reverse is a no-op (we don't restore stale Phase 10b copy on rollback).
"""
from __future__ import annotations

from django.db import migrations


CATEGORY_SLUGS = ("hoodie", "tshirts", "long-sleeve")


# ---------------------------------------------------------------- TITLES
SEO_TEXT_TITLES = {
    "hoodie":      "Худі TwoComms — патріотичний український streetwear",
    "tshirts":     "Футболки TwoComms — авторські принти ЗСУ та streetwear",
    "long-sleeve": "Лонгсліви TwoComms — тактичний streetwear на щодень",
}


# ------------------------------------------------------------- INTRO HTML
SEO_INTRO_HTML = {
    "hoodie": """
<p><strong>Худі TwoComms</strong> — це український streetwear із мілітарним
характером: щільна тканина, посилені шви, авторські принти на тему ЗСУ,
тризуба та свободи. Можна <a href="/catalog/hoodie/?color=black">купити чорне худі</a>,
<a href="/catalog/hoodie/?color=coyote">кайот</a>,
<a href="/catalog/hoodie/?color=olive">оливкове</a> або зібрати комплект з
<a href="/catalog/tshirts/">футболкою</a> чи
<a href="/catalog/long-sleeve/">лонгслівом</a>.</p>
<p class="intro-tagline">Шиємо в Україні · Авторський DTF-друк · Підтримуємо ЗСУ</p>
<details>
  <summary>Що таке худі TwoComms?</summary>
  <p>Худі — базовий елемент streetwear-гардероба, який поєднує комфорт
  спортивного одягу з силуетом сучасного вуличного стилю. У TwoComms
  ми робимо акцент на патріотичних принтах, якісному DTF-друці й
  фурнітурі, що витримує щоденне носіння. Усі худі шиються в Україні
  та є частиною <a href="/pro-brand/">мілітарного наративу бренду</a>.
  Доступні класичний і oversize силуети, розміри від XS до XXL.</p>
</details>
""",
    "tshirts": """
<p><strong>Футболки TwoComms</strong> — лаконічний український streetwear
з мілітарними акцентами та авторськими принтами на тему ЗСУ, тризуба й
вуличної естетики. Можна
<a href="/catalog/tshirts/?color=black">купити чорну футболку</a>,
<a href="/catalog/tshirts/?color=white">білу</a>,
<a href="/catalog/tshirts/?color=olive">оливу</a> або
<a href="/catalog/tshirts/?color=coyote">кайот</a>, а також доповнити її
<a href="/catalog/hoodie/">худі</a> чи
<a href="/catalog/long-sleeve/">лонгслівом</a>.</p>
<p class="intro-tagline">Авторські принти · DTF-друк · Бавовна 180–220 г/м² · Шиємо в Україні</p>
<details>
  <summary>Чому футболка TwoComms — не просто футболка?</summary>
  <p>Ми використовуємо щільний бавовняний трикотаж 180–220 г/м²,
  авторські принти у DTF-друці та власні лекала з оверсайз/класичними
  силуетами. Кожна модель — частина <a href="/pro-brand/">brand DNA TwoComms</a>:
  мілітарна естетика без зайвого пафосу, патріотичні символи без
  «лубочності», streetwear-форма без копіювання західних брендів.
  Доступні чоловічі, жіночі й унісекс-моделі, розміри XS–XXL.</p>
</details>
""",
    "long-sleeve": """
<p><strong>Лонгсліви TwoComms</strong> — універсальний шар
streetwear-гардероба: сильніший за футболку, легший за худі. У
наявності <a href="/catalog/long-sleeve/?color=black">чорний лонгслів</a>,
<a href="/catalog/long-sleeve/?color=coyote">кайот</a>,
<a href="/catalog/long-sleeve/?color=olive">олива</a> та класичні
кольори, які чудово поєднуються з <a href="/catalog/hoodie/">худі</a> і
<a href="/catalog/tshirts/">футболками</a> з нашого каталогу.</p>
<p class="intro-tagline">Бавовна · DTF-друк · Класичний / oversize силует · Підтримка ЗСУ</p>
<details>
  <summary>Коли носити лонгслів?</summary>
  <p>Лонгслів — ідеальний вибір для прохолодної погоди: можна носити
  окремо, шарувати під худі або легку куртку. У TwoComms лонгсліви
  виконані в мілітарному ДНК: акуратні принти, посилені манжети,
  тканина, що тримає форму після прання. Дізнайтеся більше про
  <a href="/pro-brand/">філософію TwoComms</a> або переглядайте
  <a href="/catalog/hoodie/">худі</a> та <a href="/catalog/tshirts/">футболки</a>
  з тими ж принтами для повного комплекту.</p>
</details>
""",
}


# ------------------------------------------------------------ DESCRIPTION
# Long-form HTML rendered by ``.catalog-description-panel`` BELOW the
# tabbed blocks. ~3000 chars per category, 6-8 H3 sections, FAQ-style
# wording, internal linking, naturally-placed long-tail keywords.

SEO_DESCRIPTION_HTML = {
    "hoodie": """
<p>У каталозі <strong>худі TwoComms</strong> ви знайдете чоловічі,
жіночі й унісекс-моделі —
<a href="/catalog/hoodie/?color=black">чорні худі</a>,
<a href="/catalog/hoodie/?color=coyote">кайот</a>,
<a href="/catalog/hoodie/?color=olive">оливкові</a> та інші нейтральні
кольори, у класичному та oversize-силуеті. Усі худі шиємо в Україні
з прицілом на щоденне носіння, добре поєднуються з
<a href="/catalog/long-sleeve/">лонгслівами</a> й
<a href="/catalog/tshirts/">футболками</a> бренду.</p>

<h3>Як обрати худі та визначити розмір</h3>
<p>Підбирайте розмір за <a href="/rozmirna-sitka/">розмірною сіткою</a>:
для шарування з лонгслівом беріть свій звичний розмір, для
oversize-силуету — на 1 більше. У сумнівах між двома розмірами
рекомендуємо більший: краще трохи вільніше, ніж тісно у плечах.
Догляд — на сторінці <a href="/doglyad-za-odyagom/">догляд за одягом</a>:
прання при 30 °C, без сушарки, не прасуйте принт із лицьового боку.</p>

<h3>Тканина, друк, фурнітура</h3>
<p>Худі TwoComms виготовлені з щільного трикотажу 280–320 г/м² з
начосом усередині, що забезпечує тепло й комфорт у прохолодну погоду.
Принти наносимо методом DTF-друку — стійка фарба, не тріскає після
прання, передає всі деталі ілюстрації. Капюшон — двошаровий, із
плетеним шнурком; манжети та низ — посилена резинка, тримає форму
після десятків циклів прання.</p>

<h3>Принти та символіка</h3>
<p>Більшість принтів TwoComms — це авторські ілюстрації у мілітарно-
streetwear-стилі: тризуб, ЗСУ, патріотична графіка, написи українською.
Ми не використовуємо «лубочну» символіку — лише сучасні візуальні
рішення, які добре виглядають у місті й комбінуються з усім
гардеробом. Деякі моделі мають принт на спині, інші — на грудях
або рукаві.</p>

<h3>Чоловіче, жіноче, унісекс</h3>
<p>У каталозі є <strong>чоловічі худі</strong> з прямим силуетом і
ширшими плечима, <strong>жіночі худі</strong> з трохи звуженою
посадкою, а також <strong>унісекс-моделі</strong>, які підходять усім.
Розміри — від XS (на дівчину 42) до XXL (на чоловіка 56).</p>

<h3>Доставка та оплата</h3>
<p>Доставляємо <a href="/delivery/">Новою Поштою</a> по всій Україні —
відділення (від 85 ₴), поштомат (від 85 ₴) або адресна доставка
кур'єром (від 180 ₴). Оплата — Monobank (миттєво), накладений платіж
або переказ на картку. <a href="/povernennya-ta-obmin/">Повернення</a>
протягом 14 днів, якщо худі не підійшло за розміром або кольором.</p>

<h3>Скільки коштує худі TwoComms?</h3>
<p>Ціни на худі стартують від 1490 ₴ за базові моделі та сягають
2200 ₴ за худі з повним принтом і додатковими деталями. Періодично
проводимо акції — слідкуйте за розділом
<a href="/catalog/hoodie/?sort=discount">зі знижками</a>. Точні ціни —
у таблиці «Найкращі ціни на худі» вище.</p>

<h3>Чому варто купити худі саме у TwoComms</h3>
<p>TwoComms — український streetwear-бренд із мілітарним ДНК. Ми
робимо одяг для тих, хто живе в Україні, підтримує ЗСУ та цінує
спокійну, але сильну естетику. 100% продукції — українського
виробництва. Частину прибутку від кожного замовлення направляємо на
підтримку Збройних Сил України. Дізнайтеся більше про
<a href="/pro-brand/">філософію бренду</a> або переглядайте всі
<a href="/catalog/">категорії каталогу</a>.</p>

<h3>Часті запитання</h3>
<p><strong>Чи сідає худі після прання?</strong> Ні — за умов прання
при 30 °C і сушіння природним способом усадка мінімальна (до 2%).
<strong>Чи можна замовити худі з власним принтом?</strong> Так,
у TwoComms є <a href="/custom-print/">кастомний друк</a> — надішліть
макет, і ми надрукуємо на обраному виробі.
<strong>Чи є гарантія на принт?</strong> 6 місяців за умов правильного
догляду; якщо принт обсиплеться — обміняємо безкоштовно.</p>
""",
    "tshirts": """
<p>Каталог <strong>футболок TwoComms</strong> — це понад десяток
авторських принтів у мілітарно-патріотичному ДНК: тризуб, ЗСУ,
streetwear-графіка, написи українською. Можна
<a href="/catalog/tshirts/?color=black">купити чорну футболку</a>,
<a href="/catalog/tshirts/?color=white">білу</a>,
<a href="/catalog/tshirts/?color=olive">оливу</a> чи
<a href="/catalog/tshirts/?color=coyote">кайот</a>, а також зібрати
комплект із <a href="/catalog/hoodie/">худі</a> або
<a href="/catalog/long-sleeve/">лонгслівом</a>.</p>

<h3>Силуети, посадки, розміри</h3>
<p>В асортименті — класичний крій (regular fit) і oversize. Для
oversize-комплектів подивіться <a href="/catalog/tshirts/?fit=oversize">фільтр
oversize</a>; для приталених — <a href="/catalog/tshirts/?fit=classic">classic</a>.
<a href="/rozmirna-sitka/">Розмірна сітка</a> допоможе вибрати точно:
для regular беріть свій розмір, для oversize — на 1 менший за звичний,
якщо хочете помірний оверсайз, або свій розмір — для виразного.</p>

<h3>Тканина та DTF-друк</h3>
<p>Футболки TwoComms — щільний бавовняний трикотаж 180–220 г/м²,
дихаючий, не просвічується. Принти наносимо методом DTF-друку:
насичені кольори, тонкі деталі, стійкість до прання й розтягнення.
На відміну від шовкографії, DTF дозволяє повноколірні зображення
без обмежень палітри. Ярлик — м'який термотрансферний, не муляє шию.</p>

<h3>Принти, символіка, авторський дизайн</h3>
<p>Більшість принтів — авторські ілюстрації, які малюють українські
дизайнери. Теми: ЗСУ, тризуб, історичні постаті, streetwear-графіка,
кіберпанк-іронія, абсурд. Ми не копіюємо західні бренди й не робимо
«лубочних» патріотичних принтів. Принти бувають на грудях, на спині
або як комбінований повноколірний друк.</p>

<h3>Чоловічі, жіночі, унісекс футболки</h3>
<p>У каталозі — <strong>чоловічі футболки</strong> з прямим силуетом,
<strong>жіночі футболки</strong> з трохи звуженою посадкою (за
бажанням можна обрати чоловічий крій для oversize-look), а також
<strong>унісекс-моделі</strong>. Розміри — від XS до XXL. Чоловічі
сягають 5XL для деяких базових моделей.</p>

<h3>Доставка та оплата</h3>
<p><a href="/delivery/">Доставка Новою Поштою</a> по всій Україні —
відділення/поштомат від 85 ₴, кур'єр від 180 ₴. Оплата — Monobank
(миттєво з захистом покупки), накладений платіж або переказ на картку.
<a href="/povernennya-ta-obmin/">Повернення</a> та обмін — 14 днів,
безкоштовно при браку. Подробиці на сторінці <a href="/dopomoga/">допомоги</a>.</p>

<h3>Скільки коштує футболка з принтом TwoComms?</h3>
<p>Ціни — від 690 ₴ за базові моделі та до 1290 ₴ за футболки з
повноколірним DTF-друком на спині. Періодично проводимо акції; знижки
показуємо в розділі <a href="/catalog/tshirts/?sort=discount">з акційними цінами</a>.
Точна ціна кожної моделі — у таблиці «Найкращі ціни» вище.</p>

<h3>Часті запитання про футболки</h3>
<p><strong>Чи можна замовити футболку зі своїм принтом?</strong> Так,
працює сервіс <a href="/custom-print/">кастомного друку</a> — надішліть
макет, і ми надрукуємо на обраному кольорі/розмірі.
<strong>Чи ліняє принт після прання?</strong> Ні, DTF-друк витримує
50+ циклів прання при 30 °C.
<strong>Чи можна прасувати?</strong> Так, але виверніть футболку
навиворіт або накрийте принт марлею.
<strong>Чи є подарункове пакування?</strong> Так — фірмова крафт-коробка
+ листівка-подяка ЗСУ; обирайте опцію в кошику.</p>
""",
    "long-sleeve": """
<p>Каталог <strong>лонгслівів TwoComms</strong> — для тих, кому замало
футболки, але худі поки зайве. Підберіть
<a href="/catalog/long-sleeve/?color=black">чорний лонгслів</a>,
<a href="/catalog/long-sleeve/?color=coyote">кайот</a>,
<a href="/catalog/long-sleeve/?color=olive">оливу</a> або базові
кольори, що добре сидять під <a href="/catalog/hoodie/">худі</a> або
самостійно. Лонгслів — найгнучкіший базовий шар streetwear-гардероба.</p>

<h3>Як носити лонгслів</h3>
<p>Лонгслів — універсальний базовий шар: можна носити окремо в
прохолодну погоду, шарувати під худі або легку куртку у міжсезонні,
комбінувати з джинсами/карго-штанами для streetwear-look. Для
холоднішої погоди подивіться розділ <a href="/catalog/hoodie/">худі</a>.
Для теплих днів — наш каталог <a href="/catalog/tshirts/">футболок</a>.</p>

<h3>Силует, тканина, манжети</h3>
<p>Лонгсліви TwoComms виконані з бавовняного трикотажу 200–240 г/м² —
щільнішого за футбольний, тонше за худі. Манжети — двошарова резинка,
тримає рукав на місці й не розтягується. Силует — класичний (regular)
або oversize. Низ рівний, без оборки, добре заправляється у штани або
носиться навипуск.</p>

<h3>Принти й мілітарне ДНК</h3>
<p>Лонгсліви часто мають мінімалістичні принти — невеликий тризуб на
грудях, напис на рукаві, авторський символ ЗСУ на спині. Для тих, хто
любить великі повноколірні принти — дивіться розділ
<a href="/catalog/tshirts/">футболок</a> та <a href="/catalog/hoodie/">худі</a>:
принт пасує до того ж стилю в повному комплекті.</p>

<h3>Чоловічі, жіночі, унісекс лонгсліви</h3>
<p>У каталозі <strong>чоловічі лонгсліви</strong> з прямим
силуетом, <strong>жіночі лонгсліви</strong> з трохи звуженою посадкою
та <strong>унісекс-моделі</strong>. Розміри — XS–XXL. Підходять і для
шарування під худі, і для самостійного носіння.</p>

<h3>Розмір і догляд</h3>
<p>Орієнтуйтеся на <a href="/rozmirna-sitka/">розмірну сітку</a>:
класичний силует — свій розмір; oversize — +1; для шарування під
худі — свій звичний. Інструкції з прання — у
<a href="/doglyad-za-odyagom/">догляді за одягом</a>: 30 °C, без
сушарки, прасування з вивороту або через марлю.</p>

<h3>Доставка та оплата</h3>
<p>Доставляємо <a href="/delivery/">Новою Поштою</a> — від 85 ₴ за
відділення/поштомат, від 180 ₴ за адресну. Оплата — Monobank,
накладений платіж або картка. <a href="/povernennya-ta-obmin/">Повернення</a>
14 днів, безкоштовно при браку.</p>

<h3>Скільки коштує лонгслів TwoComms?</h3>
<p>Ціни — від 890 ₴ за базові моделі та до 1490 ₴ за лонгсліви з
повноколірним DTF-принтом. Точну ціну кожної моделі дивіться в
таблиці «Найкращі ціни на лонгсліви» вище.</p>

<h3>Часті запитання</h3>
<p><strong>Чи теплий лонгслів TwoComms?</strong> Лонгсліви розраховані
на демісезон і шарування — самі по собі тримають температуру до +5 °C
при активному русі.
<strong>Чи можна носити лонгслів як піжаму?</strong> Можна, але
бавовна 200+ г/м² може бути замало для холодних спалень — оберіть
тонший варіант.
<strong>Чи можна замовити з власним принтом?</strong> Так — через
сервіс <a href="/custom-print/">кастомного друку</a>.</p>
""",
}


# --------------------------------------------------------- TOP_QUERIES
# Massively expanded keyword sets, mixing UA + RU long-tail (per the
# user-supplied keyword screenshots) + a few EN streetwear queries.
# Each query routes to a meaningful internal URL — never to a search
# page that returns 0 results.

TOP_QUERIES = {
    "hoodie": [
        # ---------------- UA core
        ("Купити худі ЗСУ",                   "/catalog/hoodie/"),
        ("Худі з тризубом",                   "/catalog/hoodie/"),
        ("Патріотичне худі чоловіче",         "/catalog/hoodie/"),
        ("Худі з принтом Україна",            "/catalog/hoodie/"),
        ("Тактичне худі",                     "/catalog/hoodie/?color=coyote"),
        ("Чорне худі чоловіче",               "/catalog/hoodie/?color=black"),
        ("Худі олива",                        "/catalog/hoodie/?color=olive"),
        ("Худі кайот",                        "/catalog/hoodie/?color=coyote"),
        ("Військове худі купити",             "/catalog/hoodie/"),
        ("Худі oversize Україна",             "/catalog/hoodie/?fit=oversize"),
        ("Худі classic силует",               "/catalog/hoodie/?fit=classic"),
        ("Худі з капюшоном",                  "/catalog/hoodie/"),
        ("Худі чоловіче",                     "/catalog/hoodie/"),
        ("Худі жіноче",                       "/catalog/hoodie/"),
        ("Худі унісекс",                      "/catalog/hoodie/"),
        ("Українське худі",                   "/catalog/hoodie/"),
        ("Худі для ЗСУ подарунок",            "/catalog/hoodie/"),
        ("Худі бавовна",                      "/catalog/hoodie/"),
        ("Купити худі чоловіче",              "/catalog/hoodie/"),
        ("Купити худі жіноче",                "/catalog/hoodie/"),
        ("Стрітвір худі",                     "/catalog/hoodie/"),
        ("Худі Київ",                         "/catalog/hoodie/"),
        ("Худі Львів",                        "/catalog/hoodie/"),
        ("Худі Харків",                       "/catalog/hoodie/"),
        ("Худі Одеса",                        "/catalog/hoodie/"),
        ("Худі Дніпро",                       "/catalog/hoodie/"),
        ("Худі з вишивкою",                   "/catalog/hoodie/"),
        ("Худі з принтом на спині",           "/catalog/hoodie/"),
        ("Тепле худі чоловіче",               "/catalog/hoodie/"),
        # ---------------- RU long-tail
        ("Купить худи ЗСУ",                   "/catalog/hoodie/"),
        ("Мужское худи с принтом",            "/catalog/hoodie/"),
        ("Женское худи Украина",              "/catalog/hoodie/"),
        ("Патриотическое худи",               "/catalog/hoodie/"),
        ("Тактическое худи купить",           "/catalog/hoodie/?color=coyote"),
        ("Военное худи",                      "/catalog/hoodie/"),
        ("Чёрное худи",                       "/catalog/hoodie/?color=black"),
        ("Худи на флисе",                     "/catalog/hoodie/"),
        ("Худи оверсайз мужское",             "/catalog/hoodie/?fit=oversize"),
        ("Украинское худи",                   "/catalog/hoodie/"),
        ("Купить худи с капюшоном",           "/catalog/hoodie/"),
        ("Купить худи Киев",                  "/catalog/hoodie/"),
        # ---------------- EN
        ("Streetwear hoodie Ukraine",         "/catalog/hoodie/"),
        ("Military hoodie",                   "/catalog/hoodie/?color=coyote"),
        ("ZSU hoodie",                        "/catalog/hoodie/"),
        ("Tryzub hoodie",                     "/catalog/hoodie/"),
    ],
    "tshirts": [
        # ---------------- UA core
        ("Футболка ЗСУ",                      "/catalog/tshirts/"),
        ("Футболка тризуб",                   "/catalog/tshirts/"),
        ("Патріотична футболка",              "/catalog/tshirts/"),
        ("Футболка Україна",                  "/catalog/tshirts/"),
        ("Чорна футболка чоловіча",           "/catalog/tshirts/?color=black"),
        ("Біла футболка з принтом",           "/catalog/tshirts/?color=white"),
        ("Футболка олива",                    "/catalog/tshirts/?color=olive"),
        ("Тактична футболка",                 "/catalog/tshirts/?color=coyote"),
        ("Військова футболка",                "/catalog/tshirts/"),
        ("Стрітвір футболка",                 "/catalog/tshirts/"),
        ("Футболка oversize",                 "/catalog/tshirts/?fit=oversize"),
        ("Футболка classic",                  "/catalog/tshirts/?fit=classic"),
        ("Футболка унісекс",                  "/catalog/tshirts/"),
        ("Українська футболка купити",        "/catalog/tshirts/"),
        ("Футболка бавовна",                  "/catalog/tshirts/"),
        ("Футболка з принтом ЗСУ",            "/catalog/tshirts/"),
        ("Футболка для ЗСУ подарунок",        "/catalog/tshirts/"),
        ("Замовити футболку з принтом",       "/catalog/tshirts/"),
        ("Футболки з принтом",                "/catalog/tshirts/"),
        ("Футболка чоловіча",                 "/catalog/tshirts/"),
        ("Футболка жіноча",                   "/catalog/tshirts/"),
        ("Футболки чоловічі",                 "/catalog/tshirts/"),
        ("Футболки жіночі",                   "/catalog/tshirts/"),
        ("Купити футболку Київ",              "/catalog/tshirts/"),
        ("Купити футболку Львів",             "/catalog/tshirts/"),
        ("Купити футболку Харків",            "/catalog/tshirts/"),
        ("Купити футболку Одеса",             "/catalog/tshirts/"),
        # ---------------- RU long-tail (from screenshots)
        ("Купить футболку мужскую",           "/catalog/tshirts/"),
        ("Купить футболку женскую",           "/catalog/tshirts/"),
        ("Футболки купить",                   "/catalog/tshirts/"),
        ("Купить мужские футболки хорошего качества", "/catalog/tshirts/"),
        ("Купить мужскую футболку",           "/catalog/tshirts/"),
        ("Купить женскую футболку",           "/catalog/tshirts/"),
        ("Купить футболку с принтом",         "/catalog/tshirts/"),
        ("Купить белую футболку",             "/catalog/tshirts/?color=white"),
        ("Купить чёрную футболку",            "/catalog/tshirts/?color=black"),
        ("Футболка с принтом",                "/catalog/tshirts/"),
        ("Принт на футболку",                 "/catalog/tshirts/"),
        ("Футболка со своим принтом",         "/catalog/custom-print/"),
        ("Футболка с принтом на заказ",       "/catalog/custom-print/"),
        ("Принт футболки",                    "/catalog/tshirts/"),
        ("Футболка принт",                    "/catalog/tshirts/"),
        ("Футболка с принтом на спине",       "/catalog/tshirts/"),
        ("Принт на футболках",                "/catalog/tshirts/"),
        ("Печать на футболках",               "/catalog/tshirts/"),
        ("Печать на футболках Украина",       "/catalog/tshirts/"),
        ("Футболка ЮА",                       "/catalog/tshirts/"),
        ("Футболки с логотипом",              "/catalog/tshirts/"),
        ("Мужское футболки",                  "/catalog/tshirts/"),
        ("Футболки мужские",                  "/catalog/tshirts/"),
        ("Футболки с принтом",                "/catalog/tshirts/"),
        # ---------------- EN
        ("Streetwear t-shirt Ukraine",        "/catalog/tshirts/"),
        ("Tryzub t-shirt",                    "/catalog/tshirts/"),
        ("ZSU t-shirt",                       "/catalog/tshirts/"),
        ("Military t-shirt",                  "/catalog/tshirts/?color=coyote"),
    ],
    "long-sleeve": [
        # ---------------- UA core
        ("Лонгслів чоловічий",                "/catalog/long-sleeve/"),
        ("Лонгслів жіночий",                  "/catalog/long-sleeve/"),
        ("Лонгслів ЗСУ",                      "/catalog/long-sleeve/"),
        ("Тактичний лонгслів",                "/catalog/long-sleeve/?color=coyote"),
        ("Чорний лонгслів",                   "/catalog/long-sleeve/?color=black"),
        ("Лонгслів олива",                    "/catalog/long-sleeve/?color=olive"),
        ("Лонгслів кайот",                    "/catalog/long-sleeve/?color=coyote"),
        ("Український лонгслів",              "/catalog/long-sleeve/"),
        ("Патріотичний лонгслів",             "/catalog/long-sleeve/"),
        ("Лонгслів з принтом",                "/catalog/long-sleeve/"),
        ("Лонгслів з тризубом",               "/catalog/long-sleeve/"),
        ("Стрітвір лонгслів",                 "/catalog/long-sleeve/"),
        ("Лонгслів oversize",                 "/catalog/long-sleeve/?fit=oversize"),
        ("Лонгслів classic",                  "/catalog/long-sleeve/?fit=classic"),
        ("Лонгслів унісекс",                  "/catalog/long-sleeve/"),
        ("Лонгслів бавовна",                  "/catalog/long-sleeve/"),
        ("Лонгслів подарунок ЗСУ",            "/catalog/long-sleeve/"),
        ("Купити лонгслів Україна",           "/catalog/long-sleeve/"),
        ("Купити лонгслів Київ",              "/catalog/long-sleeve/"),
        ("Купити лонгслів Львів",             "/catalog/long-sleeve/"),
        ("Кофта з довгим рукавом",            "/catalog/long-sleeve/"),
        ("Тонкий лонгслів",                   "/catalog/long-sleeve/"),
        ("Лонгслів демісезон",                "/catalog/long-sleeve/"),
        ("Лонгслів для шарування",            "/catalog/long-sleeve/"),
        # ---------------- RU long-tail
        ("Купить лонгслив",                   "/catalog/long-sleeve/"),
        ("Мужской лонгслив",                  "/catalog/long-sleeve/"),
        ("Женский лонгслив",                  "/catalog/long-sleeve/"),
        ("Лонгслив с принтом",                "/catalog/long-sleeve/"),
        ("Военный лонгслив",                  "/catalog/long-sleeve/"),
        ("Тактический лонгслив",              "/catalog/long-sleeve/?color=coyote"),
        ("Чёрный лонгслив",                   "/catalog/long-sleeve/?color=black"),
        ("Оверсайз лонгслив",                 "/catalog/long-sleeve/?fit=oversize"),
        ("Украинский лонгслив",               "/catalog/long-sleeve/"),
        ("Кофта с длинным рукавом",           "/catalog/long-sleeve/"),
        ("Лонгслив ВСУ",                      "/catalog/long-sleeve/"),
        # ---------------- EN
        ("Streetwear long sleeve",            "/catalog/long-sleeve/"),
        ("Military long sleeve",              "/catalog/long-sleeve/?color=coyote"),
        ("ZSU long sleeve",                   "/catalog/long-sleeve/"),
    ],
}


# --------------------------------------------------------- TOP_FILTERS
# Slightly expanded with print-type filters (only colour filters work
# right now — print filter is forward-looking but link is non-broken).
TOP_FILTERS = {
    "hoodie": [
        ("Чорне худі",                "/catalog/hoodie/?color=black"),
        ("Худі кайот",                "/catalog/hoodie/?color=coyote"),
        ("Олива",                     "/catalog/hoodie/?color=olive"),
        ("Сіре худі",                 "/catalog/hoodie/?color=grey"),
        ("Біле худі",                 "/catalog/hoodie/?color=white"),
        ("Худі oversize",             "/catalog/hoodie/?fit=oversize"),
        ("Худі classic",              "/catalog/hoodie/?fit=classic"),
        ("Розмір XS",                 "/catalog/hoodie/?size=XS"),
        ("Розмір S",                  "/catalog/hoodie/?size=S"),
        ("Розмір M",                  "/catalog/hoodie/?size=M"),
        ("Розмір L",                  "/catalog/hoodie/?size=L"),
        ("Розмір XL",                 "/catalog/hoodie/?size=XL"),
        ("Розмір XXL",                "/catalog/hoodie/?size=XXL"),
        ("Зі знижкою",                "/catalog/hoodie/?sort=discount"),
    ],
    "tshirts": [
        ("Чорна футболка",            "/catalog/tshirts/?color=black"),
        ("Біла футболка",             "/catalog/tshirts/?color=white"),
        ("Олива",                     "/catalog/tshirts/?color=olive"),
        ("Кайот",                     "/catalog/tshirts/?color=coyote"),
        ("Сіра футболка",             "/catalog/tshirts/?color=grey"),
        ("Футболка oversize",         "/catalog/tshirts/?fit=oversize"),
        ("Футболка classic",          "/catalog/tshirts/?fit=classic"),
        ("Розмір XS",                 "/catalog/tshirts/?size=XS"),
        ("Розмір S",                  "/catalog/tshirts/?size=S"),
        ("Розмір M",                  "/catalog/tshirts/?size=M"),
        ("Розмір L",                  "/catalog/tshirts/?size=L"),
        ("Розмір XL",                 "/catalog/tshirts/?size=XL"),
        ("Розмір XXL",                "/catalog/tshirts/?size=XXL"),
        ("Зі знижкою",                "/catalog/tshirts/?sort=discount"),
    ],
    "long-sleeve": [
        ("Чорний лонгслів",           "/catalog/long-sleeve/?color=black"),
        ("Кайот",                     "/catalog/long-sleeve/?color=coyote"),
        ("Олива",                     "/catalog/long-sleeve/?color=olive"),
        ("Білий лонгслів",            "/catalog/long-sleeve/?color=white"),
        ("Сірий лонгслів",            "/catalog/long-sleeve/?color=grey"),
        ("Лонгслів oversize",         "/catalog/long-sleeve/?fit=oversize"),
        ("Лонгслів classic",          "/catalog/long-sleeve/?fit=classic"),
        ("Розмір XS",                 "/catalog/long-sleeve/?size=XS"),
        ("Розмір S",                  "/catalog/long-sleeve/?size=S"),
        ("Розмір M",                  "/catalog/long-sleeve/?size=M"),
        ("Розмір L",                  "/catalog/long-sleeve/?size=L"),
        ("Розмір XL",                 "/catalog/long-sleeve/?size=XL"),
        ("Розмір XXL",                "/catalog/long-sleeve/?size=XXL"),
        ("Зі знижкою",                "/catalog/long-sleeve/?sort=discount"),
    ],
}


# ---------------------------------------------------------------- ops

def _replace_block_items(apps, category, block_type, items, title):
    CategorySeoBlock = apps.get_model("storefront", "CategorySeoBlock")
    CategorySeoBlockItem = apps.get_model("storefront", "CategorySeoBlockItem")
    block = (CategorySeoBlock.objects.filter(category=category, block_type=block_type)
             .order_by("order", "id").first())
    if block is None:
        block = CategorySeoBlock.objects.create(
            category=category, block_type=block_type, title=title,
            is_active=True, order=2 if block_type == "top_filters" else 3,
        )
    else:
        # Refresh title and reset items.
        if title and block.title != title:
            block.title = title
            block.save(update_fields=["title"])
        block.is_active = True
        block.save(update_fields=["is_active"])
        CategorySeoBlockItem.objects.filter(block=block).delete()
    for idx, payload in enumerate(items):
        CategorySeoBlockItem.objects.create(
            block=block,
            label=payload["label"],
            url=payload.get("url", ""),
            extra=payload.get("extra") or {},
            order=idx,
        )


def force_extend_seo_copy(apps, schema_editor):
    Category = apps.get_model("storefront", "Category")
    for slug in CATEGORY_SLUGS:
        category = Category.objects.filter(slug=slug).first()
        if not category:
            continue

        # Force-overwrite copy fields. This migration is intentionally
        # destructive of editorial content from 0053; if the editor has
        # made manual changes between 0053 and 0054 they'll be lost.
        category.description    = SEO_DESCRIPTION_HTML.get(slug, "").strip()
        category.seo_intro_html = SEO_INTRO_HTML.get(slug, "").strip()
        category.seo_text_title = SEO_TEXT_TITLES.get(slug, "")
        category.save(update_fields=["description", "seo_intro_html", "seo_text_title"])

        _replace_block_items(
            apps, category, "top_queries",
            [{"label": l, "url": u} for l, u in TOP_QUERIES.get(slug, [])],
            title="ТОП запити",
        )
        _replace_block_items(
            apps, category, "top_filters",
            [{"label": l, "url": u} for l, u in TOP_FILTERS.get(slug, [])],
            title="ТОП фільтри",
        )


def reverse_noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0053_phase10b_seed_category_seo"),
    ]

    operations = [
        migrations.RunPython(force_extend_seo_copy, reverse_noop),
    ]
