import json
import os
import subprocess
import sys
import tempfile
import textwrap
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from orders.models import Order


class IgOrderAssignmentModelTests(TestCase):
    def setUp(self):
        from management.models import IgClient

        self.actor = get_user_model().objects.create_user(
            username="assignment-manager",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client = IgClient.get_or_create_for_sender("assignment-client")
        self.other_client = IgClient.get_or_create_for_sender("assignment-other")
        self.order = Order.objects.create(
            full_name="Website buyer",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            total_sum=790,
            payment_status="paid",
            source="website",
            sale_source="Website",
        )

    def _assignment(self):
        from management.models import IgOrderAssignment

        return IgOrderAssignment.objects.create(
            order=self.order,
            client=self.client,
            source=IgOrderAssignment.Source.MANAGER_MANUAL,
            assigned_by=self.actor,
        )

    def test_order_has_one_current_assignment_projection(self):
        from management.models import IgOrderAssignment

        self._assignment()
        with self.assertRaises(IntegrityError):
            with self.captureOnCommitCallbacks(execute=True):
                IgOrderAssignment.objects.create(
                    order=self.order,
                    client=self.other_client,
                    source=IgOrderAssignment.Source.MANAGER_MANUAL,
                )

    def test_assignment_defaults_to_version_one(self):
        assignment = self._assignment()

        self.assertEqual(assignment.version, 1)
        self.assertIsNone(assignment.unassigned_at)

        with self.assertRaises(ValueError):
            assignment.delete()
        with self.assertRaises(ValueError):
            type(assignment).objects.filter(pk=assignment.pk).delete()
        with self.assertRaises(ValueError):
            type(assignment).objects.filter(pk=assignment.pk)._raw_delete("default")

    def test_assignment_event_is_append_only(self):
        from management.models import IgOrderAssignmentEvent

        assignment = self._assignment()
        event = IgOrderAssignmentEvent.objects.create(
            operation_id=uuid.uuid4(),
            assignment=assignment,
            order=self.order,
            kind=IgOrderAssignmentEvent.Kind.LINKED,
            to_client=self.client,
            actor=self.actor,
            actor_source=IgOrderAssignmentEvent.ActorSource.MANAGEMENT_USER,
            assignment_source=assignment.source,
            assignment_version=assignment.version,
        )

        event.reason = "changed"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()
        with self.assertRaises(ValueError):
            IgOrderAssignmentEvent.objects.filter(pk=event.pk).update(reason="changed")
        with self.assertRaises(ValueError):
            IgOrderAssignmentEvent.objects.bulk_update([event], ["reason"])
        with self.assertRaises(ValueError):
            IgOrderAssignmentEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(ValueError):
            IgOrderAssignmentEvent.objects.filter(pk=event.pk)._raw_delete("default")

    def test_operation_id_is_unique(self):
        from management.models import IgOrderAssignmentEvent

        assignment = self._assignment()
        operation_id = uuid.uuid4()
        payload = {
            "operation_id": operation_id,
            "assignment": assignment,
            "order": self.order,
            "kind": IgOrderAssignmentEvent.Kind.LINKED,
            "to_client": self.client,
            "actor": self.actor,
            "actor_source": IgOrderAssignmentEvent.ActorSource.MANAGEMENT_USER,
            "assignment_source": assignment.source,
            "assignment_version": assignment.version,
        }
        IgOrderAssignmentEvent.objects.create(**payload)

        with self.assertRaises(IntegrityError):
            IgOrderAssignmentEvent.objects.create(**payload)

    def test_customer_event_key_is_unique(self):
        from management.models import IgOrderCustomerEvent

        assignment = self._assignment()
        payload = {
            "event_key": f"order:{self.order.pk}:ttn:hash",
            "assignment": assignment,
            "assignment_version": assignment.version,
            "order": self.order,
            "client": self.client,
            "kind": IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
            "locale": "en",
            "message_snapshot": "Your order has been shipped.",
            "payload": {"tracking_number": "20400000000000"},
        }
        IgOrderCustomerEvent.objects.create(**payload)

        with self.assertRaises(IntegrityError):
            IgOrderCustomerEvent.objects.create(**payload)

    def test_customer_event_identity_is_immutable_but_state_is_mutable(self):
        from management.models import IgOrderCustomerEvent

        assignment = self._assignment()
        event = IgOrderCustomerEvent.objects.create(
            event_key=f"order:{self.order.pk}:ttn:immutable",
            assignment=assignment,
            assignment_version=assignment.version,
            order=self.order,
            client=self.client,
            kind=IgOrderCustomerEvent.Kind.TTN_ASSIGNED,
            locale="en",
            message_snapshot="Your order has been shipped.",
            payload={"tracking_number": "20400000000000"},
        )

        event.state = IgOrderCustomerEvent.State.SENT
        event.save(update_fields=["state"])
        self.assertEqual(
            IgOrderCustomerEvent.objects.get(pk=event.pk).state,
            IgOrderCustomerEvent.State.SENT,
        )

        event.event_key = "order:rewritten"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            IgOrderCustomerEvent.objects.filter(pk=event.pk).update(
                event_key="order:rewritten"
            )
        with self.assertRaises(ValueError):
            IgOrderCustomerEvent.objects.bulk_update([event], ["event_key"])
        with self.assertRaises(ValueError):
            event.delete()
        with self.assertRaises(ValueError):
            IgOrderCustomerEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(ValueError):
            IgOrderCustomerEvent.objects.filter(pk=event.pk)._raw_delete("default")


class IgOrderAssignmentMigrationTests(SimpleTestCase):
    def test_legacy_attribution_backfill_is_guarded_and_reversible(self):
        script = textwrap.dedent(
            """
            import importlib
            import json
            import os
            import sys

            os.environ["DJANGO_SETTINGS_MODULE"] = "twocomms.settings"
            from django.conf import settings

            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sys.argv[1],
            }

            import django
            django.setup()

            from django.db import DatabaseError, connection
            from django.db.migrations.executor import MigrationExecutor

            migrate_from = ("management", "0118_ig_funnel_reset_audit")
            migrate_to = ("management", "0119_ig_order_assignments")

            executor = MigrationExecutor(connection)
            executor.migrate([migrate_from])
            executor = MigrationExecutor(connection)
            old_apps = executor.loader.project_state([migrate_from]).apps

            Client = old_apps.get_model("management", "IgClient")
            Attribution = old_apps.get_model("management", "IgOrderAttribution")
            Order = old_apps.get_model("orders", "Order")

            client = Client.objects.create(
                igsid="legacy-assignment-client",
                stage="order_created",
            )
            order = Order.objects.create(
                full_name="Legacy Instagram buyer",
                phone="380501112233",
                city="Kyiv",
                np_office="Branch 1",
                total_sum="790.00",
                payment_status="paid",
                source="instagram",
                sale_source="Instagram",
            )
            attribution = Attribution.objects.create(
                order_id=order.pk,
                client_id=client.pk,
                creation_mode="linked_existing",
                payment_source="unknown",
            )
            attribution_created_at = attribution.created_at

            executor = MigrationExecutor(connection)
            executor.migrate([migrate_to])
            executor = MigrationExecutor(connection)
            new_apps = executor.loader.project_state([migrate_to]).apps
            Assignment = new_apps.get_model("management", "IgOrderAssignment")
            Event = new_apps.get_model("management", "IgOrderAssignmentEvent")
            CustomerEvent = new_apps.get_model("management", "IgOrderCustomerEvent")

            assignment = Assignment.objects.get(order_id=order.pk)
            event = Event.objects.get(assignment_id=assignment.pk)
            migration = importlib.import_module(
                "management.migrations.0119_ig_order_assignments"
            )
            with connection.schema_editor() as schema_editor:
                migration.drop_assignment_event_guards(new_apps, schema_editor)
                Event.objects.filter(pk=event.pk).delete()
                migration.backfill_assignments(new_apps, schema_editor)
                migration.create_assignment_event_guards(new_apps, schema_editor)
            event = Event.objects.get(assignment_id=assignment.pk)
            customer_event = CustomerEvent.objects.create(
                event_key=f"order:{order.pk}:ttn:migration",
                assignment_id=assignment.pk,
                assignment_version=assignment.version,
                order_id=order.pk,
                client_id=client.pk,
                kind="ttn_assigned",
                locale="en",
                message_snapshot="Your order has been shipped.",
                payload={"tracking_number": "20400000000000"},
            )

            update_guarded = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE management_igorderassignmentevent "
                        "SET reason = %s WHERE id = %s",
                        ["changed", event.pk],
                    )
            except DatabaseError:
                update_guarded = True

            delete_guarded = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM management_igorderassignmentevent WHERE id = %s",
                        [event.pk],
                    )
            except DatabaseError:
                delete_guarded = True

            customer_update_guarded = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE management_igordercustomerevent "
                        "SET event_key = %s WHERE id = %s",
                        ["order:rewritten", customer_event.pk],
                    )
            except DatabaseError:
                customer_update_guarded = True

            customer_state_update_allowed = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE management_igordercustomerevent "
                        "SET state = %s WHERE id = %s",
                        ["sent", customer_event.pk],
                    )
                customer_state_update_allowed = True
            except DatabaseError:
                customer_state_update_allowed = False

            customer_delete_guarded = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM management_igordercustomerevent WHERE id = %s",
                        [customer_event.pk],
                    )
            except DatabaseError:
                customer_delete_guarded = True

            with connection.schema_editor() as schema_editor:
                migration.drop_assignment_event_guards(new_apps, schema_editor)
                migration.reverse_backfill_assignments(new_apps, schema_editor)

            after_handler = {
                "assignments": Assignment.objects.count(),
                "events": Event.objects.count(),
                "customer_events": CustomerEvent.objects.count(),
                "attributions": new_apps.get_model(
                    "management", "IgOrderAttribution"
                ).objects.count(),
                "payment_status": new_apps.get_model(
                    "orders", "Order"
                ).objects.get(pk=order.pk).payment_status,
            }

            executor = MigrationExecutor(connection)
            executor.migrate([migrate_from])
            executor = MigrationExecutor(connection)
            reverted_apps = executor.loader.project_state([migrate_from]).apps

            print("MIGRATION_RESULT=" + json.dumps({
                "forward": {
                    "source": assignment.source,
                    "client_matches": assignment.client_id == client.pk,
                    "version": assignment.version,
                    "assigned_at_preserved": assignment.assigned_at == attribution_created_at,
                    "event_kind": event.kind,
                    "actor_source": event.actor_source,
                    "event_version": event.assignment_version,
                    "snapshot_matches": event.snapshot["attribution_id"] == attribution.pk,
                },
                "db_guards": {
                    "update": update_guarded,
                    "delete": delete_guarded,
                    "customer_update": customer_update_guarded,
                    "customer_state_update_allowed": customer_state_update_allowed,
                    "customer_delete": customer_delete_guarded,
                },
                "after_handler": after_handler,
                "after_migration_reverse": {
                    "attributions": reverted_apps.get_model(
                        "management", "IgOrderAttribution"
                    ).objects.count(),
                    "orders": reverted_apps.get_model("orders", "Order").objects.count(),
                    "payment_status": reverted_apps.get_model(
                        "orders", "Order"
                    ).objects.get(pk=order.pk).payment_status,
                },
            }, sort_keys=True))
            """
        )
        project_root = os.path.dirname(os.path.dirname(__file__))
        env = os.environ.copy()
        for key in (
            "DB_ENGINE",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
            "DB_PORT",
        ):
            env.pop(key, None)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (project_root, env.get("PYTHONPATH", "")))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "migration.sqlite3")
            result = subprocess.run(
                [sys.executable, "-c", script, database_path],
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        marker = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("MIGRATION_RESULT=")
        )
        payload = json.loads(marker.removeprefix("MIGRATION_RESULT="))
        self.assertEqual(
            payload["forward"],
            {
                "source": "manager_manual",
                "client_matches": True,
                "version": 1,
                "assigned_at_preserved": True,
                "event_kind": "linked",
                "actor_source": "migration",
                "event_version": 1,
                "snapshot_matches": True,
            },
        )
        self.assertEqual(
            payload["db_guards"],
            {
                "update": True,
                "delete": True,
                "customer_update": True,
                "customer_state_update_allowed": True,
                "customer_delete": True,
            },
        )
        self.assertEqual(
            payload["after_handler"],
            {
                "assignments": 1,
                "events": 1,
                "customer_events": 1,
                "attributions": 1,
                "payment_status": "paid",
            },
        )
        self.assertEqual(
            payload["after_migration_reverse"],
            {"attributions": 1, "orders": 1, "payment_status": "paid"},
        )
