import argparse

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import update

from app.database import get_session_factory
from app.models import Role, User
from app.schemas import EmailAddress


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the role of a registered account")
    parser.add_argument("email")
    parser.add_argument("role", choices=[role.value for role in Role])
    args = parser.parse_args()
    try:
        email = TypeAdapter(EmailAddress).validate_python(args.email)
    except ValidationError:
        parser.error("Invalid email address")

    with get_session_factory().begin() as db:
        user_id = db.scalar(
            update(User).where(User.email == email).values(role=Role(args.role)).returning(User.id)
        )
        if user_id is None:
            parser.exit(1, "Account not found\n")

    print(f"Role set to {args.role} for {email}")


if __name__ == "__main__":
    main()
