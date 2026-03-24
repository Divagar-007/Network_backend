# routes/jobs.py
# Job posting CRUD and search

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from database.db import get_db
from models.models import Job, User
from schemas.schemas import JobCreate, JobOut
from utils.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new job post. Any authenticated user can post a job."""
    job = Job(**payload.model_dump(), poster_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return db.query(Job).options(joinedload(Job.poster)).filter(Job.id == job.id).first()


@router.get("/", response_model=List[JobOut])
def list_jobs(
    q: Optional[str]     = Query(None, description="Search title, skills, or role"),
    skill: Optional[str] = Query(None),
    role: Optional[str]  = Query(None),
    location: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    skip: int  = 0,
    limit: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    List/search active jobs.
    Supports free-text search across title, skills, and role,
    plus individual filter params.
    """
    query = db.query(Job).options(joinedload(Job.poster)).filter(Job.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            Job.title.ilike(like) |
            Job.skills.ilike(like) |
            Job.role.ilike(like)  |
            Job.company.ilike(like)
        )
    if skill:
        query = query.filter(Job.skills.ilike(f"%{skill}%"))
    if role:
        query = query.filter(Job.role.ilike(f"%{role}%"))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(Job.job_type.ilike(f"%{job_type}%"))

    return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Return a single job by ID."""
    job = db.query(Job).options(joinedload(Job.poster)).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a job post (poster only)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.poster_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job post")
    db.delete(job)
    db.commit()


    db.delete(job)
    db.commit()
