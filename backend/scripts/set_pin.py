"""Хэрэглэгчийн ПИН кодыг олноор нь тохируулах туслах скрипт.

Хэрэглээ (backend хавтаснаас):

    python -m scripts.set_pin 000000            # БҮХ хэрэглэгчид
    python -m scripts.set_pin 4821 dorj         # зөвхөн нэг хэрэглэгчид
    python -m scripts.set_pin 4821 dorj tuya    # хэд хэдэн хэрэглэгчид

Анхаар: бүх хэрэглэгч нэг ПИН-тэй бол аудит логоос хэн үйлдэл хийснийг
ялгах боломжгүй болно. Ашиглалтад оруулахын өмнө тус тусад нь солино уу.
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.security import hash_pin


def _validate(pin: str) -> str:
    """Router-ийн `_validate_pin`-тэй ижил дүрэм (4–6 орон, зөвхөн тоо)."""
    pin = (pin or "").strip()
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise SystemExit("ПИН нь зөвхөн тоо, 4–6 оронтой байх ёстой.")
    return pin


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    pin = _validate(sys.argv[1])
    usernames = sys.argv[2:]

    async with async_session_factory() as db:
        stmt = select(User)
        if usernames:
            stmt = stmt.where(User.username.in_(usernames))
        users = (await db.scalars(stmt)).all()

        if not users:
            raise SystemExit("Хэрэглэгч олдсонгүй.")

        pin_hash = hash_pin(pin)
        for user in users:
            user.pin_hash = pin_hash
            print(f"  {user.username:<8} {user.full_name:<8} ПИН: {pin}")
        await db.commit()

    print(f"\n{len(users)} хэрэглэгчийн ПИН шинэчлэгдлээ.")


if __name__ == "__main__":
    asyncio.run(main())
