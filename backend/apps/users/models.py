"""Модели пользователей и RBAC (SPEC §2, §10.2, §12).

Домен ``users`` — центральный: определяет пользователя (custom AUTH_USER_MODEL),
роли и разрешения. Все остальные домены опираются на RBAC при контроле доступа.

Ролевая модель (SPEC §2.1):
- HR-администратор — полный доступ к агрегатам, управлению пользователями/ролями;
- Руководитель — свои циклы оценки, подчинённые (агрегированно);
- Сотрудник — проходит оценку, даёт ОС, самооценка;
- Методолог/Куратор — курсы, материалы, модели компетенций.

Принципы (SPEC §2.2):
- гранулярные права на действия и объекты;
- принцип минимума привилегий;
- составные роли (несколько ролей на одного пользователя суммируют права).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import QuerySet


class UserManager(BaseUserManager["User"]):
    """Менеджер пользователей для входа по email (без username).

    ``create_user``/``create_superuser`` принимают email вместо username.
    """

    use_in_migrations = True

    def _create_user(
        self,
        email: str,
        password: str | None,
        **extra_fields: object,
    ) -> User:
        """Создать и сохранить пользователя с email и паролем."""
        if not email:
            msg = "Email обязателен для пользователя"
            raise ValueError(msg)
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: object) -> User:
        """Создать обычного пользователя (не staff, не superuser)."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> User:
        """Создать суперпользователя (для manage.py createsuperuser)."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            msg = "Суперпользователь должен иметь is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Суперпользователь должен иметь is_superuser=True."
            raise ValueError(msg)
        return self._create_user(email, password, **extra_fields)


class Role(models.Model):
    """Роль пользователя в системе (SPEC §2.1).

    Роли предустановлены и соответствуют бизнес-ролям. ``code`` — стабильный
    идентификатор для ссылок в коде (см. ``RoleCode`` в permissions.py).
    """

    class Code(models.TextChoices):
        """Стабильные коды ролей для использования в коде."""

        HR = "hr", _("HR-администратор")
        MANAGER = "manager", _("Руководитель")
        EMPLOYEE = "employee", _("Сотрудник")
        METHODOLOGIST = "methodologist", _("Методолог/Куратор")

    code = models.CharField(
        _("Код роли"),
        max_length=32,
        choices=Code.choices,
        unique=True,
    )
    name = models.CharField(_("Название"), max_length=100)
    description = models.TextField(_("Описание"), blank=True)

    class Meta:
        verbose_name = _("Роль")
        verbose_name_plural = _("Роли")
        ordering = ["code"]

    def __str__(self) -> str:
        """Человеческое представление роли."""
        return self.name


class Permission(models.Model):
    """Гранулярное разрешение на действие (SPEC §2.2).

    ``code`` — точечное право, например ``assessment.cycle.manage``.
    Роли связываются с разрешениями через ``RolePermission`` (M2M c весом/контекстом
    не нужен — достаточно простой связи: роль = набор разрешений).
    """

    code = models.CharField(
        _("Код разрешения"),
        max_length=128,
        unique=True,
        help_text=_("Например: assessment.cycle.manage"),
    )
    name = models.CharField(_("Название"), max_length=200)
    roles: models.ManyToManyField[Role, RolePermission] = models.ManyToManyField(
        Role,
        related_name="permissions",
        through="RolePermission",
        verbose_name=_("Роли"),
    )

    class Meta:
        verbose_name = _("Разрешение")
        verbose_name_plural = _("Разрешения")
        ordering = ["code"]

    def __str__(self) -> str:
        """Код разрешения как идентификатор."""
        return self.code


class RolePermission(models.Model):
    """Связь роли и разрешения (явная через-модель для будущих расширений)."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name=_("Роль"))
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, verbose_name=_("Разрешение")
    )

    class Meta:
        verbose_name = _("Право роли")
        verbose_name_plural = _("Права ролей")
        unique_together = [("role", "permission")]

    def __str__(self) -> str:
        """Роль → разрешение."""
        return f"{self.role.code} → {self.permission.code}"


class User(AbstractUser):
    """Пользователь системы (custom AUTH_USER_MODEL, SPEC §10.2).

    Расширяет ``AbstractUser``: дополнительно хранит связь с AD-учёткой (для SSO),
    роли (составные — несколько ролей суммируют права, SPEC §2.2) и флаг
    локального пароля (запасной механизм при недоступности AD).

    ПДн: ФИО и email сотрудника хранятся здесь и в связанном Employee
    (домен orgstructure). Шифрование и комплаенс — SPEC §12.
    """

    # Вход по email (SPEC §3.3), username-поле не нужно.
    username = None  # type: ignore[assignment]
    email = models.EmailField(_("Email"), unique=True)

    # Кастомный менеджер: create_user/create_superuser по email.
    objects = UserManager()  # type: ignore[assignment,misc]

    # Связь с корпоративной учёткой (AD/LDAP). None — локальный пользователь.
    ad_account = models.CharField(
        _("Учётная запись AD/LDAP"),
        max_length=128,
        blank=True,
        unique=True,
        null=True,
        help_text=_("sAMAccountName или эквивалент. Пусто — локальный вход по паролю."),
    )

    # Флаг: разрешён ли запасной локальный пароль (для внешних консультантов).
    local_login_enabled = models.BooleanField(
        _("Локальный вход разрешён"),
        default=False,
        help_text=_("Запасной механизм при недоступности AD или для консультантов."),
    )

    # Составные роли: пользователь может иметь несколько ролей одновременно.
    roles = models.ManyToManyField(
        Role,
        related_name="users",
        blank=True,
        verbose_name=_("Роли"),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # type: ignore[misc]

    class Meta:
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")
        ordering = ["email"]

    def __str__(self) -> str:
        """Email как идентификатор пользователя."""
        return self.email

    # ---- RBAC: разрешения суммируются по всем ролям пользователя ----
    def get_all_permission_codes(self) -> set[str]:
        """Множество кодов разрешений, доступных пользователю (по всем ролям).

        Составные роли суммируются (SPEC §2.2): если пользователь —
        руководитель И куратор, его права — объединение прав обеих ролей.
        """
        role_ids: Iterable[int] = self.roles.values_list("id", flat=True)
        return set(
            Permission.objects.filter(roles__in=list(role_ids))
            .values_list("code", flat=True)
            .distinct()
        )

    def has_permission(self, code: str) -> bool:
        """Есть ли у пользователя конкретное разрешение (по коду)."""
        return code in self.get_all_permission_codes()

    def has_any_role(self, *role_codes: str) -> bool:
        """Есть ли у пользователя хотя бы одна из перечисленных ролей (по кодам)."""
        if not role_codes:
            return False
        return self.roles.filter(code__in=role_codes).exists()

    def is_hr(self) -> bool:
        """Является ли HR-администратором."""
        return self.has_any_role(Role.Code.HR.value)

    def is_manager(self) -> bool:
        """Является ли руководителем."""
        return self.has_any_role(Role.Code.MANAGER.value)


def get_default_roles() -> QuerySet[Role]:
    """Дефолтный запрос ролей (для удобства в фикстурах/миграциях)."""
    return Role.objects.all()
