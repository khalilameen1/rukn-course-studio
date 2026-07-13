from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.crud import courses
from app.db import get_session
from app.routers.deps import get_course_or_404
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseRead, status_code=201)
def create_course(payload: CourseCreate, session: Session = Depends(get_session)):
    return courses.create(session, **payload.model_dump())


@router.get("", response_model=list[CourseRead])
def list_courses(session: Session = Depends(get_session)):
    return courses.list(session)


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: int, session: Session = Depends(get_session)):
    return get_course_or_404(session, course_id)


@router.put("/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int, payload: CourseUpdate, session: Session = Depends(get_session)
):
    get_course_or_404(session, course_id)
    return courses.update(session, course_id, **payload.model_dump(exclude_unset=True))
