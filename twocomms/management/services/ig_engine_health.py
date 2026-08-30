"""Инвентаризация storage engine для таблиц, участвующих в блокировках (Э0.2).

В коде много `select_for_update()`. На MyISAM row-lock и rollback не работают
вообще: код выглядит корректным, а гарантии нет. Поэтому атомарность stage
(Э3.2), атомарная запись `sales_context` (Э3.11), транзакции lifecycle (Э2.7) и
бюджет соединений (Э8.1) заблокированы этой проверкой.

**Ограничение прежнего инструмента, которое пришлось убрать.** Команда
`audit_ig_table_engines` читала жёсткий список `IG_RUNTIME_TABLES`. Список уже был
шире базового, но не доказывал полноту: новая commerce/post-sale таблица в нём
просто отсутствовала, и отчёт получался формально зелёным и неполным. Поэтому
candidate set теперь выводится **из Django model metadata**, а константа
проверяется на полноту относительно него.
"""
from __future__ import annotations

import re
from pathlib import Path

IG_RUNTIME_TABLES = (
    "management_igclient",
    "management_igclientstageevent",
    "management_igconversationsignal",
    "management_igconversationanalysissnapshot",
    "management_igconversationanalysisjob",
    "management_geminikeystate",
    "management_geminimodelquotausage",
    "management_geminimodelstate",
    "management_geminiquotaprofile",
    "management_geminiquotastate",
    "management_geminirequest",
    "management_geminirequestattempt",
    "management_igaireplyrecoveryjob",
    "management_igpermissiontransitionjob",
    "management_igdeal",
    "management_igdealitem",
    "management_igfollowuptask",
    "management_igmetaeventlog",
    "management_igbotnotification",
    "management_igbotnotificationaudit",
    "management_instagrambotlog",
    "management_instagrambotmessage",
    "management_instagrambotprocessedmessage",
    "management_instagrambotrawevent",
    "management_instagrambotsettings",
    # Assisted checkout and the transactional parents it locks/refs. Keeping
    # these in the read-only audit makes the MariaDB preflight fail before a
    # migration can create a partial FK graph.
    "management_igcheckoutproposal",
    "management_igcheckoutaccesstoken",
    "management_igcheckoutproposalitem",
    "management_igcheckoutinventoryreservation",
    "management_igcheckoutinvoicegeneration",
    "management_igcheckoutinvoicegenerationevent",
    "management_igcheckoutrevision",
    "management_iglifecycleevent",
    "management_igpaymentevent",
    "management_igorderattribution",
    "management_igcommercialepisode",
    # Э0.2: раньше эти таблицы участвовали в блокировках и НЕ входили в список,
    # из-за чего отчёт был формально зелёным и неполным.
    "management_igpostsalecase",
    "management_igordershipment",
    "management_igcommerceselectionsession",
    "management_igcommerceselectiontransition",
    "management_igcommerceturndecision",
    "management_igcommercemanagerreview",
    "management_igpaymentprojection",
    "management_igpaymentconfirmationreview",
    "management_igpaymentreviewdecision",
    "management_igorderassignment",
    "management_igorderassignmentevent",
    "management_igorderlinkevent",
    "management_igordercustomerevent",
    "management_igugcreward",
    "management_igugcrewardlifetime",
    "management_igugcrewarddelivery",
    "management_igugcrewardlifecyclejob",
    "management_igugcevidenceassessment",
    "management_igfollowstate",
    "management_igfollowcapabilitystate",
    "management_igfollowrefreshjob",
    "management_igfollowctadecision",
    "management_igpaymentfollowpreparation",
    "management_igdealinvoicelifecycle",
    "management_iginboxrefreshrun",
    "management_iginboxrefreshitem",
    "management_igpollcursor",
    "management_igfunnelresetaudit",
    "management_igcommercialepisodeevent",
    "management_igfunnelstepevent",
    "management_igfunneldropoff",
    "management_igobjection",
    "management_igobjectionattempt",
    "management_iganalysismaterialityevent",
    "management_igconversationanalysisresult",
    "management_iganalysisproposal",
    "management_igconversationanalysisevent",
    "management_igproviderincident",
    "management_igclientdegradationepisode",
    "management_igcustomerturn",
    "management_igturnmessage",
    "management_igfollowobservation",
    "management_instagrambottaskheartbeat",
    "management_botinstruction",
    "management_botpromptrevision",
    "orders_order",
    "orders_paymentattempt",
)

# Префиксы моделей приложения `management`, образующих IG-runtime.
_IG_MODEL_PREFIXES = ("Ig", "InstagramBot", "Gemini", "BotInstruction", "BotPromptRevision")
# Таблицы за пределами `management`, которые IG-путь блокирует напрямую.
_EXTERNAL_LOCKED_TABLES = ("orders_order", "orders_paymentattempt")

_SELECT_FOR_UPDATE_RE = re.compile(r"([A-Za-z_][\w.]*)\s*\.\s*objects[^\n]{0,200}?select_for_update")
_LOCK_SCAN_DIRS = ("services", "management/commands")


def ig_runtime_candidate_tables() -> tuple:
    """Candidate set из Django model metadata, а не из константы.

    Именно это отвечает на вопрос полноты: новая commerce/post-sale модель
    попадает в набор автоматически, и её отсутствие в `IG_RUNTIME_TABLES`
    становится видимым числом, а не незамеченной дыркой.
    """
    from django.apps import apps

    tables = set(_EXTERNAL_LOCKED_TABLES)
    for model in apps.get_app_config("management").get_models():
        if model._meta.proxy or not model._meta.managed:
            continue
        if model.__name__.startswith(_IG_MODEL_PREFIXES):
            tables.add(model._meta.db_table)
    return tuple(sorted(tables))


def runtime_table_gaps() -> dict:
    """Расхождение между candidate set и объявленной константой."""
    candidates = set(ig_runtime_candidate_tables())
    declared = set(IG_RUNTIME_TABLES)
    return {
        "missing_from_constant": tuple(sorted(candidates - declared)),
        "declared_but_unknown": tuple(sorted(declared - candidates)),
        "candidate_count": len(candidates),
        "declared_count": len(declared),
    }


def select_for_update_sites(base_dir=None) -> dict:
    """Где в коде реально берётся row-lock.

    Статический скан, а не предположение: `lock contract` в отчёте должен
    опираться на найденные места вызова, иначе колонка ничего не доказывает.
    Скан по именам моделей в выражении `Model.objects...select_for_update(...)`;
    он не претендует на полноту по косвенным путям и это отмечено в отчёте.
    """
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    sites: dict = {}
    for relative in _LOCK_SCAN_DIRS:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in _SELECT_FOR_UPDATE_RE.finditer(source):
                model_name = match.group(1).split(".")[-1]
                sites.setdefault(model_name, set()).add(path.name)
    return {name: tuple(sorted(files)) for name, files in sorted(sites.items())}


def model_table_by_name() -> dict:
    from django.apps import apps

    mapping = {}
    for config in apps.get_app_configs():
        for model in config.get_models():
            mapping.setdefault(model.__name__, model._meta.db_table)
    return mapping
