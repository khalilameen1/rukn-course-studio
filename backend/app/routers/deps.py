from fastapi import HTTPException
from sqlmodel import Session

from app.crud import courses
from app.models.course import Course


def get_course_or_404(session: Session, course_id: int) -> Course:
    course = courses.get(session, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
