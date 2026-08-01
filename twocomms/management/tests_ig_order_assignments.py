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
from django.utils import timezone

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
        from management.services.ig_order_assignments import link_order_to_client

        return link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
        )

    def test_direct_assignment_create_is_rejected_outside_service(self):
        from management.models import IgOrderAssignment

        with self.assertRaisesRegex(ValueError, "assignment service"):
            IgOrderAssignment.objects.create(
                order=self.order,
                client=self.client,
                source=IgOrderAssignment.Source.MANAGER_MANUAL,
            )

    def test_direct_assignment_save_and_queryset_updates_are_rejected(self):
        from management.models import IgOrderAssignment

        assignment = self._assignment()
        assignment.client = self.other_client
        with self.assertRaisesRegex(ValueError, "assignment service"):
            assignment.save(update_fields=["client", "updated_at"])
        with self.assertRaisesRegex(ValueError, "assignment service"):
            IgOrderAssignment.objects.filter(pk=assignment.pk).update(
                client=self.other_client
            )
        with self.assertRaisesRegex(ValueError, "assignment service"):
            IgOrderAssignment.objects.bulk_update([assignment], ["client"])

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

    def test_link_exact_order_is_idempotent_and_audited(self):
        from management.models import IgOrderAssignment, IgOrderAssignmentEvent
        from management.services.ig_order_assignments import link_order_to_client

        operation_id = uuid.uuid4()
        first = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
            source=IgOrderAssignment.Source.MANAGER_MANUAL,
            operation_id=operation_id,
        )
        replay = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
            source=IgOrderAssignment.Source.MANAGER_MANUAL,
            operation_id=operation_id,
        )

        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(
            IgOrderAssignmentEvent.objects.filter(order=self.order).count(),
            1,
        )
        self.assertEqual(first.version, 1)

    def test_link_rejects_another_current_owner(self):
        from management.services.ig_order_assignments import (
            AssignmentConflict,
            link_order_to_client,
        )

        link_order_to_client(self.order, client=self.client, actor=self.actor)
        with self.assertRaises(AssignmentConflict):
            link_order_to_client(
                self.order,
                client=self.other_client,
                actor=self.actor,
            )

    def test_operation_id_cannot_be_reused_for_another_action_or_client(self):
        from management.services.ig_order_assignments import (
            OrderAssignmentError,
            link_order_to_client,
            unlink_order_from_client,
        )

        operation_id = uuid.uuid4()
        assignment = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
            operation_id=operation_id,
        )
        with self.assertRaises(OrderAssignmentError):
            link_order_to_client(
                self.order,
                client=self.other_client,
                actor=self.actor,
                operation_id=operation_id,
            )
        with self.assertRaises(OrderAssignmentError):
            unlink_order_from_client(
                self.order,
                client=self.client,
                actor=self.actor,
                operation_id=operation_id,
                expected_version=assignment.version,
                reason_code="manager_correction",
                reason="Wrong action id",
            )

    def test_link_rejects_legacy_attribution_owner_before_projection_backfill(self):
        from management.models import IgOrderAttribution
        from management.services.ig_order_assignments import (
            AssignmentConflict,
            link_order_to_client,
        )

        IgOrderAttribution.objects.create(
            order=self.order,
            client=self.other_client,
            creation_mode="linked_existing",
            payment_source="unknown",
        )
        with self.assertRaises(AssignmentConflict):
            link_order_to_client(self.order, client=self.client, actor=self.actor)

    def test_explicit_unlink_allows_relink_despite_historical_attribution(self):
        from management.models import IgOrderAttribution
        from management.services.ig_order_assignments import (
            link_order_to_client,
            unlink_order_from_client,
        )

        IgOrderAttribution.objects.create(
            order=self.order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="unknown",
        )
        assignment = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
        )
        unlink_order_from_client(
            self.order,
            client=self.client,
            actor=self.actor,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="Website order was matched to the wrong Instagram customer.",
        )

        relinked = link_order_to_client(
            self.order,
            client=self.other_client,
            actor=self.actor,
            expected_version=2,
        )

        self.assertEqual(relinked.client_id, self.other_client.pk)
        self.assertEqual(relinked.version, 3)

    def test_unlink_rejects_request_from_another_client(self):
        from management.services.ig_order_assignments import (
            AssignmentConflict,
            link_order_to_client,
            unlink_order_from_client,
        )

        assignment = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
        )

        with self.assertRaises(AssignmentConflict):
            unlink_order_from_client(
                self.order,
                client=self.other_client,
                actor=self.actor,
                expected_version=assignment.version,
                reason_code="manager_correction",
                reason="Wrong drawer attempted the unlink.",
            )

    def test_first_link_rejects_a_stale_expected_version(self):
        from management.services.ig_order_assignments import (
            AssignmentVersionConflict,
            link_order_to_client,
        )

        with self.assertRaises(AssignmentVersionConflict):
            link_order_to_client(
                self.order,
                client=self.client,
                actor=self.actor,
                expected_version=7,
            )

    def test_link_rejects_cancelled_order_and_hidden_client(self):
        from management.services.ig_order_assignments import (
            OrderAssignmentError,
            link_order_to_client,
        )

        self.order.status = "cancelled"
        self.order.save(update_fields=["status"])
        with self.assertRaises(OrderAssignmentError):
            link_order_to_client(self.order, client=self.client, actor=self.actor)

        self.order.status = "new"
        self.order.save(update_fields=["status"])
        self.client.hidden_at = timezone.now()
        self.client.save(update_fields=["hidden_at", "updated_at"])
        with self.assertRaises(OrderAssignmentError):
            link_order_to_client(self.order, client=self.client, actor=self.actor)

    def test_unlink_requires_reason_and_expected_version_then_allows_relink(self):
        from management.models import IgOrderAssignment, IgOrderAssignmentEvent
        from management.services.ig_order_assignments import (
            AssignmentVersionConflict,
            link_order_to_client,
            unlink_order_from_client,
        )

        assignment = link_order_to_client(
            self.order,
            client=self.client,
            actor=self.actor,
        )
        with self.assertRaises(ValueError):
            unlink_order_from_client(
                self.order,
                client=self.client,
                actor=self.actor,
                expected_version=assignment.version,
            )
        unlink_order_from_client(
            self.order,
            client=self.client,
            actor=self.actor,
            expected_version=assignment.version,
            reason_code="manager_correction",
            reason="The manager selected the wrong Instagram client.",
        )
        cleared = IgOrderAssignment.objects.get(order=self.order)
        self.assertIsNone(cleared.client_id)
        self.assertEqual(cleared.version, 2)
        with self.assertRaises(AssignmentVersionConflict):
            unlink_order_from_client(
                self.order,
                client=self.client,
                actor=self.actor,
                expected_version=1,
                reason_code="manager_correction",
                reason="stale action",
            )
        relinked = link_order_to_client(
            self.order,
            client=self.other_client,
            actor=self.actor,
            source=IgOrderAssignment.Source.MANAGER_MANUAL,
            expected_version=cleared.version,
        )
        self.assertEqual(relinked.client_id, self.other_client.pk)
        self.assertEqual(relinked.version, 3)
        self.assertEqual(
            IgOrderAssignmentEvent.objects.filter(order=self.order).count(),
            3,
        )

    def test_provider_attribution_creates_automatic_assignment_without_payment_mutation(self):
        from management.models import IgOrderAssignment, IgOrderAssignmentEvent
        from management.services.ig_order_links import create_order_attribution

        before = {
            "payment_status": self.order.payment_status,
            "total_sum": self.order.total_sum,
        }
        create_order_attribution(
            self.order,
            client=self.client,
            creation_mode="provider_auto",
            payment_source="provider_monobank",
        )
        assignment = IgOrderAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.client_id, self.client.pk)
        self.assertEqual(assignment.source, IgOrderAssignment.Source.PROVIDER_AUTO)
        self.assertEqual(
            IgOrderAssignmentEvent.objects.get(order=self.order).actor_source,
            IgOrderAssignmentEvent.ActorSource.AUTOMATION,
        )
        self.assertEqual(
            IgOrderAssignmentEvent.objects.get(order=self.order).kind,
            IgOrderAssignmentEvent.Kind.AUTO_CONFIRMED,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, before["payment_status"])
        self.assertEqual(self.order.total_sum, before["total_sum"])

    def test_conflicting_automatic_attribution_rolls_back_without_split_ownership(self):
        from management.models import IgOrderAttribution
        from management.services.ig_order_assignments import (
            AssignmentConflict,
            link_order_to_client,
        )
        from management.services.ig_order_links import create_order_attribution

        link_order_to_client(self.order, client=self.client, actor=self.actor)
        with self.assertRaises(AssignmentConflict):
            create_order_attribution(
                self.order,
                client=self.other_client,
                creation_mode="provider_auto",
                payment_source="provider_monobank",
            )

        self.assertFalse(IgOrderAttribution.objects.filter(order=self.order).exists())


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
