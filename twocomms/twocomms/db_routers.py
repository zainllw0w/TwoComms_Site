from django.conf import settings


class DtfDatabaseRouter:
    """
    Optional router for isolating DTF app data into DATABASES['dtf'].

    Auth/users remain in default DB to keep shared login between main domain
    and DTF subdomain. DTF models are routed to `dtf` only when alias exists.
    """

    dtf_alias = "dtf"
    dtf_apps = {"dtf"}
    shared_meta_apps = {"auth", "contenttypes"}

    def _enabled(self) -> bool:
        return self.dtf_alias in getattr(settings, "DATABASES", {})

    def db_for_read(self, model, **hints):
        if self._enabled() and model._meta.app_label in self.dtf_apps:
            return self.dtf_alias
        return None

    def db_for_write(self, model, **hints):
        if self._enabled() and model._meta.app_label in self.dtf_apps:
            return self.dtf_alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if not self._enabled():
            return None
        if obj1._meta.app_label in self.dtf_apps or obj2._meta.app_label in self.dtf_apps:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if not self._enabled():
            return None

        if app_label in self.dtf_apps:
            return db == self.dtf_alias

        if app_label in self.shared_meta_apps:
            return db in {"default", self.dtf_alias}

        if db == self.dtf_alias:
            return False
        return True
