from django.db import models


class SyntheticMigrationDrift(models.Model):
    value = models.CharField(max_length=64)
