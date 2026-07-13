from datetime import datetime, timezone
from typing import Any, Generic, Optional, Type, TypeVar

from sqlmodel import Session, SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class CRUDBase(Generic[ModelType]):
    """Minimal, explicit CRUD helper for one SQLModel table.

    Deliberately not a "framework": one small generic class, no magic, so
    each model's CRUD module (see app/crud/course.py etc.) stays a one-line
    instantiation instead of five copy-pasted functions per model.
    """

    def __init__(self, model: Type[ModelType]) -> None:
        self.model = model

    def create(self, session: Session, **fields: Any) -> ModelType:
        obj = self.model(**fields)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

    def get(self, session: Session, id_: int) -> Optional[ModelType]:
        return session.get(self.model, id_)

    def list(self, session: Session, **equals: Any) -> list[ModelType]:
        """List all rows, optionally filtered by exact column equality.

        Example: `crud_course_source.list(session, course_id=3)`
        """
        statement = select(self.model)
        for column_name, value in equals.items():
            statement = statement.where(getattr(self.model, column_name) == value)
        return list(session.exec(statement))

    def update(self, session: Session, id_: int, **fields: Any) -> Optional[ModelType]:
        obj = self.get(session, id_)
        if obj is None:
            return None
        for field_name, value in fields.items():
            setattr(obj, field_name, value)
        if hasattr(obj, "updated_at"):
            obj.updated_at = datetime.now(timezone.utc)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

    def delete(self, session: Session, id_: int) -> bool:
        obj = self.get(session, id_)
        if obj is None:
            return False
        session.delete(obj)
        session.commit()
        return True
