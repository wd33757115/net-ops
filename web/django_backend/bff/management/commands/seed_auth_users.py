"""创建演示用户与 RBAC 分组。"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

DEMO_USERS = [
    ("admin", "admin123", "admin", True),
    ("operator", "operator123", "operator", False),
    ("viewer", "viewer123", "viewer", False),
]


class Command(BaseCommand):
    help = "创建 admin/operator/viewer 演示账号与 Django Group"

    def handle(self, *args, **options):
        for group_name in ("admin", "operator", "viewer"):
            Group.objects.get_or_create(name=group_name)
            self.stdout.write(f"Group ready: {group_name}")

        for username, password, group_name, is_staff in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@local"})
            user.set_password(password)
            user.is_staff = is_staff
            user.is_superuser = group_name == "admin"
            user.save()
            group = Group.objects.get(name=group_name)
            user.groups.set([group])
            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"User {username} {action} (role={group_name})"))

        self.stdout.write("")
        self.stdout.write("演示账号：admin/admin123 | operator/operator123 | viewer/viewer123")
