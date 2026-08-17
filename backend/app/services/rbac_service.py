"""Эрх, дүрийн синк — кодод тодорхойлсныг өгөгдлийн санд тусгана.

`app/permissions.py`-д шинэ эрх нэмэхэд суусан систем дээр өөрөө үйлчилдэг
байх ёстой. Seed нь зөвхөн ХООСОН санд ажилладаг тул шинэчлэлтийн дараа
эрх нэмэгдэхгүй үлддэг байв — иймд аппликейшн асах бүрд энэ синк ажиллана.

Идемпотент: зөвхөн ДУТУУ эрх, дүрийн холбоосыг нэмнэ. Гараар авсан эрхийг
хасахгүй (эзэн дүрд нэмэлт эрх өгсөн бол хэвээр үлдэнэ).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Permission, Role, RolePermission
from app.permissions import PERMISSIONS, ROLE_NAMES_MN, ROLE_PERMISSIONS

log = logging.getLogger("rbac")


async def sync_permissions(db: AsyncSession) -> dict[str, Role]:
    """Эрх, дүр, дүр-эрхийн холбоосыг кодтой тэнцүүлнэ. Дүрүүдийг буцаана."""
    existing_perms = {p.code: p for p in (await db.scalars(select(Permission))).all()}
    added_perms = 0
    for code, name in PERMISSIONS.items():
        perm = existing_perms.get(code)
        if perm is None:
            perm = Permission(code=code, name_mn=name)
            db.add(perm)
            existing_perms[code] = perm
            added_perms += 1
        elif perm.name_mn != name:
            perm.name_mn = name
    await db.flush()

    roles: dict[str, Role] = {r.code: r for r in (await db.scalars(select(Role))).all()}
    added_links = 0
    for code, perm_codes in ROLE_PERMISSIONS.items():
        role = roles.get(code)
        if role is None:
            role = Role(code=code, name_mn=ROLE_NAMES_MN[code])
            db.add(role)
            await db.flush()
            roles[code] = role
        elif role.name_mn != ROLE_NAMES_MN[code]:
            # Нэршил өөрчлөгдсөн бол (Кассчин → Түгээгч) байгаа мөрийг шинэчилнэ.
            role.name_mn = ROLE_NAMES_MN[code]

        current = {
            rp.permission_id
            for rp in (
                await db.scalars(select(RolePermission).where(RolePermission.role_id == role.id))
            ).all()
        }
        for pc in perm_codes:
            perm = existing_perms[pc]
            if perm.id not in current:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
                added_links += 1
    await db.flush()

    if added_perms or added_links:
        log.info("Эрхийн синк: %d шинэ эрх, %d шинэ холбоос", added_perms, added_links)
    return roles
