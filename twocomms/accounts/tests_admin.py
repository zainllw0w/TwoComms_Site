from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from accounts.admin import UserAdmin


class UserAdminQueryOptimizationTests(TestCase):
    def test_list_display_related_values_use_one_query_and_allow_missing_rows(self):
        users = [
            User.objects.create_user(username=f"admin-query-{index}")
            for index in range(10)
        ]
        for index, user in enumerate(users):
            user.userprofile.phone = f"+3809900000{index:02d}"
            user.userprofile.save(update_fields=["phone"])
            user.points.points = index
            user.points.save(update_fields=["points"])

        users[0].userprofile.delete()
        users[1].points.delete()

        request = RequestFactory().get("/admin/auth/user/")
        model_admin = UserAdmin(User, AdminSite())

        with self.assertNumQueries(1):
            rows = list(model_admin.get_queryset(request).order_by("id"))
            values = [
                (model_admin.user_phone(user), str(model_admin.user_points(user)))
                for user in rows
            ]

        self.assertEqual(values[0][0], "—")
        self.assertEqual(values[1][1], "—")
        self.assertEqual(values[2][0], "+380990000002")
        self.assertIn("2 балів", values[2][1])
