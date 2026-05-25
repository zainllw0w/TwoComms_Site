from django.db import migrations


def polish_veteran_fund_article(apps, schema_editor):
    BlogPost = apps.get_model("storefront", "BlogPost")
    db_alias = schema_editor.connection.alias
    try:
        post = BlogPost.objects.using(db_alias).get(slug="twocomms-veteran-fund-progress")
    except BlogPost.DoesNotExist:
        return

    uk_content = """
<section class="article-lede-panel">
  <p>Підтримка Українського ветеранського фонду стала для TwoComms не просто знаком довіри, а реальним виробничим бустом. Завдяки цій підтримці ми посилили власне виробництво, пришвидшили роботу з принтами і зробили якість більш контрольованою всередині бренда.</p>
</section>
<h2>Підтримка фонду, яка перетворюється на продукт</h2>
<p>TwoComms будує бренд не навколо випадкових принтів, а навколо характеру, історії і якості. Український ветеранський фонд допоміг нам рухатися саме в цьому напрямі: не залежати повністю від підрядників, не чекати чужих виробничих черг і не приймати компроміси там, де клієнт має отримати чіткий результат.</p>
<div class="article-callout type-info">
  <div class="callout-icon"><i class="fas fa-hands-helping" aria-hidden="true"></i></div>
  <div class="callout-content"><strong>Що змінилося для клієнта:</strong> швидший запуск принтів, більше контролю над кольором і деталями, можливість замовляти кастомні ідеї не як виняток, а як нормальний напрям TwoComms.</div>
</div>
<h2>Власний DTF-друк: якість, швидкість і контроль</h2>
<p>Окремий фокус розвитку — власний DTF-друк. Це технологічне обладнання, яке дає змогу переносити складну графіку на речі з високою деталізацією, стабільною передачею кольору і прогнозованою якістю. Для технічного контексту: професійні голови класу Epson I3200 використовують PrecisionCore MicroTFP і мають 3200 сопел, що напряму важливо для точності та стабільності друку.</p>
<div class="article-tech-specs">
  <div><span>DTF</span><strong>власний друк</strong><p>Менше залежності від аутсорсу і більше контролю на кожному етапі.</p></div>
  <div><span>I3200</span><strong>3200 сопел</strong><p>Клас друкувальних голів для точного нанесення і стабільної деталізації.</p></div>
  <div><span>Color</span><strong>контроль кольору</strong><p>Можливість краще тримати насиченість, контраст і повторюваність принта.</p></div>
</div>
<h2>Що вже закрито: 2 з 4 етапів</h2>
<p>За внутрішнім планом TwoComms уже закрито 2 з 4 етапів. Другий етап посилив виробничу дисципліну, продуктивність і напрям кастомних принтів. Це не фінальна точка, а база, на якій далі зростатимуть нові матеріали, відео, B2B-напрям і колаборації.</p>
<div class="article-stage-board">
  <div class="stage-card done"><span>01</span><strong>База виробництва</strong><p>Процеси, підготовка речей, контроль якості і робоча логіка виробництва.</p></div>
  <div class="stage-card done"><span>02</span><strong>Власний DTF і кастом</strong><p>Окремий напрям для персональних принтів, командного мерчу і швидших тестів.</p></div>
  <div class="stage-card"><span>03</span><strong>B2B і матеріали</strong><p>Готові DTF-плівки, нові варіанти матеріалів і зрозуміліший формат замовлень.</p></div>
  <div class="stage-card"><span>04</span><strong>Відео і прозорість</strong><p>Покажемо процеси детальніше: друк, перенесення, догляд і реальні приклади.</p></div>
</div>
<h2>B2C: кастомні принти для людей</h2>
<p>Для клієнтів це означає простішу можливість зробити річ під себе: символ, фразу, знак команди, ідею для подарунка або власний мінімерч. Ми хочемо, щоб кастомний принт був не складною послугою “десь збоку”, а нормальним сценарієм у TwoComms.</p>
<div class="article-action-box">
  <a href="/custom-print/" class="article-action-btn">Створити кастомний принт <i class="fas fa-arrow-right" aria-hidden="true"></i></a>
</div>
<h2>B2B: DTF-плівка і мерч для підрозділів</h2>
<p>Власне обладнання відкриває і B2B-напрям: готова DTF-плівка, друк під задачі команд, маленьких брендів, майстерень і військових підрозділів. Якщо потрібна плівка для переносу, серія принтів або мерч під ключ — з нами можна напряму звʼязатися і обговорити задачу.</p>
<div class="article-cta-row">
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fab fa-telegram" aria-hidden="true"></i>
    <span>Замовити DTF-плівку</span>
    <em>Написати в Telegram</em>
  </a>
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fas fa-users" aria-hidden="true"></i>
    <span>Обговорити колаборацію</span>
    <em>Мерч, принти, спільні дропи</em>
  </a>
</div>
<h2>Колаборації з військовими частинами</h2>
<p>Окремий напрям, який для нас важливий, — брендований мерч для підрозділів і колаборації з військовими частинами. Ми вже готуємо формати, де можна буде поєднувати айдентику підрозділу, авторський стиль TwoComms і якісний DTF-друк без зайвого аутсорсу. Далі ми зможемо показувати приклади з шевронами, логотипами і готовими рішеннями.</p>
<blockquote>
  <p>Фонд допоміг нам перейти від ідеї “зробити принт” до сильнішої виробничої системи: швидше тестувати, якісніше друкувати і точніше відповідати за готову річ.</p>
  <cite>TwoComms editorial</cite>
</blockquote>
<h2>Що буде далі</h2>
<p>Наступні етапи будуть про масштаб, нові матеріали, відеоогляди і більш прозорий показ процесу. Ми хочемо, щоб люди бачили не тільки готову річ, а й те, як вона створюється: від ідеї до принта, від принта до одягу, від одягу до історії бренда.</p>
"""
    ru_content = """
<section class="article-lede-panel">
  <p>Поддержка Украинского ветеранского фонда стала для TwoComms не просто знаком доверия, а реальным производственным бустом. Благодаря этой поддержке мы усилили собственное производство, ускорили работу с принтами и сделали качество более контролируемым внутри бренда.</p>
</section>
<h2>Поддержка фонда, которая превращается в продукт</h2>
<p>TwoComms строит бренд не вокруг случайных принтов, а вокруг характера, истории и качества. Украинский ветеранский фонд помог нам двигаться именно в этом направлении: меньше зависеть от подрядчиков, не ждать чужих производственных очередей и не принимать компромиссы там, где клиент должен получить четкий результат.</p>
<div class="article-callout type-info">
  <div class="callout-icon"><i class="fas fa-hands-helping" aria-hidden="true"></i></div>
  <div class="callout-content"><strong>Что изменилось для клиента:</strong> быстрее запуск принтов, больше контроля над цветом и деталями, возможность заказывать кастомные идеи не как исключение, а как нормальное направление TwoComms.</div>
</div>
<h2>Собственный DTF-печать: качество, скорость и контроль</h2>
<p>Отдельный фокус развития — собственная DTF-печать. Это технологичное оборудование, которое позволяет переносить сложную графику на вещи с высокой детализацией, стабильной передачей цвета и прогнозируемым качеством. Для технического контекста: профессиональные головы класса Epson I3200 используют PrecisionCore MicroTFP и имеют 3200 сопел, что важно для точности и стабильности печати.</p>
<div class="article-tech-specs">
  <div><span>DTF</span><strong>собственная печать</strong><p>Меньше зависимости от аутсорса и больше контроля на каждом этапе.</p></div>
  <div><span>I3200</span><strong>3200 сопел</strong><p>Класс печатающих голов для точного нанесения и стабильной детализации.</p></div>
  <div><span>Color</span><strong>контроль цвета</strong><p>Возможность лучше держать насыщенность, контраст и повторяемость принта.</p></div>
</div>
<h2>Что уже закрыто: 2 из 4 этапов</h2>
<p>По внутреннему плану TwoComms уже закрыто 2 из 4 этапов. Второй этап усилил производственную дисциплину, продуктивность и направление кастомных принтов. Это не финальная точка, а база для новых материалов, видео, B2B-направления и коллабораций.</p>
<div class="article-stage-board">
  <div class="stage-card done"><span>01</span><strong>База производства</strong><p>Процессы, подготовка вещей, контроль качества и рабочая логика производства.</p></div>
  <div class="stage-card done"><span>02</span><strong>Собственный DTF и кастом</strong><p>Отдельное направление для персональных принтов, командного мерча и быстрых тестов.</p></div>
  <div class="stage-card"><span>03</span><strong>B2B и материалы</strong><p>Готовые DTF-пленки, новые варианты материалов и более понятный формат заказов.</p></div>
  <div class="stage-card"><span>04</span><strong>Видео и прозрачность</strong><p>Покажем процессы подробнее: печать, перенос, уход и реальные примеры.</p></div>
</div>
<h2>B2C: кастомные принты для людей</h2>
<p>Для клиентов это означает более простой способ сделать вещь под себя: символ, фразу, знак команды, идею для подарка или собственный минимерч. Мы хотим, чтобы кастомный принт был не сложной услугой “где-то сбоку”, а нормальным сценарием в TwoComms.</p>
<div class="article-action-box">
  <a href="/custom-print/" class="article-action-btn">Создать кастомный принт <i class="fas fa-arrow-right" aria-hidden="true"></i></a>
</div>
<h2>B2B: DTF-пленка и мерч для подразделений</h2>
<p>Собственное оборудование открывает и B2B-направление: готовая DTF-пленка, печать под задачи команд, маленьких брендов, мастерских и военных подразделений. Если нужна пленка для переноса, серия принтов или мерч под ключ — с нами можно напрямую связаться и обсудить задачу.</p>
<div class="article-cta-row">
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fab fa-telegram" aria-hidden="true"></i>
    <span>Заказать DTF-пленку</span>
    <em>Написать в Telegram</em>
  </a>
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fas fa-users" aria-hidden="true"></i>
    <span>Обсудить коллаборацию</span>
    <em>Мерч, принты, общие дропы</em>
  </a>
</div>
<h2>Коллаборации с военными частями</h2>
<p>Отдельное направление, которое для нас важно, — брендированный мерч для подразделений и коллаборации с военными частями. Мы уже готовим форматы, где можно будет соединять айдентику подразделения, авторский стиль TwoComms и качественную DTF-печать без лишнего аутсорса.</p>
<blockquote>
  <p>Фонд помог нам перейти от идеи “сделать принт” к более сильной производственной системе: быстрее тестировать, качественнее печатать и точнее отвечать за готовую вещь.</p>
  <cite>TwoComms editorial</cite>
</blockquote>
<h2>Что будет дальше</h2>
<p>Следующие этапы будут про масштаб, новые материалы, видеообзоры и более прозрачный показ процесса. Мы хотим, чтобы люди видели не только готовую вещь, но и то, как она создается: от идеи до принта, от принта до одежды, от одежды до истории бренда.</p>
"""
    en_content = """
<section class="article-lede-panel">
  <p>Support from the Ukrainian Veterans Fund became more than a sign of trust for TwoComms. It became a real production boost: stronger in-house processes, faster print work and more control over final quality.</p>
</section>
<h2>Support that turns into product quality</h2>
<p>TwoComms is not building a brand around random prints. The brand is built around character, story and quality. The Ukrainian Veterans Fund helped us move in that direction: less dependency on contractors, fewer external production delays and fewer compromises where the customer should receive a clear result.</p>
<div class="article-callout type-info">
  <div class="callout-icon"><i class="fas fa-hands-helping" aria-hidden="true"></i></div>
  <div class="callout-content"><strong>What changes for the customer:</strong> faster print launches, more control over colour and detail, and custom ideas becoming a normal TwoComms direction instead of an exception.</div>
</div>
<h2>In-house DTF printing: quality, speed and control</h2>
<p>A separate focus is in-house DTF printing. This production equipment helps transfer complex graphics to apparel with high detail, stable colour and predictable quality. For technical context, professional Epson I3200-class heads use PrecisionCore MicroTFP technology and have 3,200 nozzles, which matters for print accuracy and consistency.</p>
<div class="article-tech-specs">
  <div><span>DTF</span><strong>in-house print</strong><p>Less outsourcing dependency and more control at each stage.</p></div>
  <div><span>I3200</span><strong>3,200 nozzles</strong><p>A printhead class built for precise output and stable detail.</p></div>
  <div><span>Color</span><strong>colour control</strong><p>Better control of saturation, contrast and repeatability.</p></div>
</div>
<h2>What is closed now: 2 of 4 stages</h2>
<p>According to the internal TwoComms roadmap, 2 of 4 stages are already complete. The second stage strengthened production discipline, productivity and custom printing. This is not the final point, but a base for new materials, video, B2B and collaborations.</p>
<div class="article-stage-board">
  <div class="stage-card done"><span>01</span><strong>Production base</strong><p>Processes, garment preparation, quality control and production logic.</p></div>
  <div class="stage-card done"><span>02</span><strong>In-house DTF and custom</strong><p>A separate direction for personal prints, team merch and faster tests.</p></div>
  <div class="stage-card"><span>03</span><strong>B2B and materials</strong><p>Ready DTF films, new material options and a clearer ordering format.</p></div>
  <div class="stage-card"><span>04</span><strong>Video and clarity</strong><p>More visibility into printing, transfer, care and real examples.</p></div>
</div>
<h2>B2C: custom prints for people</h2>
<p>For customers, this means an easier way to create a personal piece: a symbol, phrase, team mark, gift idea or small merch set. We want custom print to be a normal TwoComms scenario, not a complicated side service.</p>
<div class="article-action-box">
  <a href="/custom-print/" class="article-action-btn">Create a custom print <i class="fas fa-arrow-right" aria-hidden="true"></i></a>
</div>
<h2>B2B: DTF film and unit merch</h2>
<p>In-house equipment also opens a B2B direction: ready DTF film, printing for teams, small brands, workshops and military units. If you need transfer film, a print series or turnkey merch, you can contact us directly and discuss the task.</p>
<div class="article-cta-row">
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fab fa-telegram" aria-hidden="true"></i>
    <span>Order DTF film</span>
    <em>Message us on Telegram</em>
  </a>
  <a href="https://t.me/twocomms" target="_blank" rel="noopener" class="article-link-card">
    <i class="fas fa-users" aria-hidden="true"></i>
    <span>Discuss a collaboration</span>
    <em>Merch, prints, joint drops</em>
  </a>
</div>
<h2>Collaborations with military units</h2>
<p>A separate direction we care about is branded merch for units and collaborations with military formations. We are preparing formats where unit identity, TwoComms style and quality DTF printing can work together without unnecessary outsourcing.</p>
<blockquote>
  <p>The fund helped us move from “making a print” to a stronger production system: faster testing, better printing and clearer responsibility for the finished piece.</p>
  <cite>TwoComms editorial</cite>
</blockquote>
<h2>What comes next</h2>
<p>The next stages are about scale, new materials, video reviews and clearer process visibility. We want people to see not only the finished piece, but how it is created: from idea to print, from print to apparel, from apparel to brand story.</p>
"""
    fields = {
        "title": "TwoComms і Український ветеранський фонд: власний DTF-друк і нові можливості",
        "title_uk": "TwoComms і Український ветеранський фонд: власний DTF-друк і нові можливості",
        "title_ru": "TwoComms и Украинский ветеранский фонд: собственная DTF-печать и новые возможности",
        "title_en": "TwoComms and the Ukrainian Veterans Fund: in-house DTF printing and new capabilities",
        "excerpt": "Підтримка Українського ветеранського фонду допомогла TwoComms посилити власний DTF-друк, якість, швидкість, кастомні принти, B2B-напрям і колаборації.",
        "excerpt_uk": "Підтримка Українського ветеранського фонду допомогла TwoComms посилити власний DTF-друк, якість, швидкість, кастомні принти, B2B-напрям і колаборації.",
        "excerpt_ru": "Поддержка Украинского ветеранского фонда помогла TwoComms усилить собственную DTF-печать, качество, скорость, кастомные принты, B2B-направление и коллаборации.",
        "excerpt_en": "Support from the Ukrainian Veterans Fund helped TwoComms strengthen in-house DTF printing, quality, speed, custom prints, B2B and collaborations.",
        "content_html": uk_content.strip(),
        "content_html_uk": uk_content.strip(),
        "content_html_ru": ru_content.strip(),
        "content_html_en": en_content.strip(),
        "seo_title": "TwoComms і Український ветеранський фонд: власний DTF-друк",
        "seo_title_uk": "TwoComms і Український ветеранський фонд: власний DTF-друк",
        "seo_title_ru": "TwoComms и Украинский ветеранский фонд: собственная DTF-печать",
        "seo_title_en": "TwoComms and Ukrainian Veterans Fund: in-house DTF printing",
        "seo_description": "Як підтримка Українського ветеранського фонду посилила TwoComms: власний DTF-друк, контроль якості, кастомні принти, B2B-плівка і колаборації.",
        "seo_description_uk": "Як підтримка Українського ветеранського фонду посилила TwoComms: власний DTF-друк, контроль якості, кастомні принти, B2B-плівка і колаборації.",
        "seo_description_ru": "Как поддержка Украинского ветеранского фонда усилила TwoComms: собственная DTF-печать, контроль качества, кастомные принты, B2B-пленка и коллаборации.",
        "seo_description_en": "How support from the Ukrainian Veterans Fund strengthened TwoComms: in-house DTF printing, quality control, custom prints, B2B film and collaborations.",
        "seo_keywords": "TwoComms, Український ветеранський фонд, DTF друк, кастомні принти, DTF плівка, мерч для підрозділів",
        "cta_label": "Написати в Telegram",
        "cta_label_uk": "Написати в Telegram",
        "cta_label_ru": "Написать в Telegram",
        "cta_label_en": "Message us on Telegram",
        "cta_url": "https://t.me/twocomms",
        "cta_text": "Для DTF-плівки, мерчу під ключ, колаборації або ідеї принта напишіть нам напряму — обговоримо задачу і формат.",
        "cta_text_uk": "Для DTF-плівки, мерчу під ключ, колаборації або ідеї принта напишіть нам напряму — обговоримо задачу і формат.",
        "cta_text_ru": "Для DTF-пленки, мерча под ключ, коллаборации или идеи принта напишите нам напрямую — обсудим задачу и формат.",
        "cta_text_en": "For DTF film, turnkey merch, collaborations or print ideas, message us directly and we will discuss the task and format.",
    }
    for field, value in fields.items():
        if hasattr(post, field):
            setattr(post, field, value)
    post.save(using=db_alias)


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0070_blogpost_cta_label_blogpost_cta_label_en_and_more"),
    ]

    operations = [
        migrations.RunPython(polish_veteran_fund_article, migrations.RunPython.noop),
    ]
