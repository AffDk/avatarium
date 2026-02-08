"""Project and Photo API routes per contracts/api.yaml."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.database import get_db
from backend.models.project import Person, Photo, Project
from backend.schemas.auth import UserResponse
from backend.schemas.project import (
    CreateProjectRequest,
    PersonResponse,
    PhotoGroupResponse,
    PhotoResponse,
    PhotoUploadResponse,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
)
from backend.services.upload_service import (
    parse_filename,
    save_photo_file,
    validate_file,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# ── Helpers ──────────────────────────────────────────────


async def _get_user_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """Fetch a project ensuring it belongs to the current user."""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.persons).selectinload(Person.photos))
        .where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ── Project CRUD ─────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    body: CreateProjectRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new video project."""
    project = Project(
        user_id=current_user.id,
        title=body.title,
        video_style=body.video_style,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = 1,
    per_page: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List current user's projects with pagination."""
    # Count total
    count_q = select(func.count(Project.id)).where(Project.user_id == current_user.id)
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Fetch page
    offset = (page - 1) * per_page
    q = (
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(q)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        page=page,
        per_page=per_page,
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetailResponse:
    """Get project detail with persons and photos."""
    project = await _get_user_project(project_id, current_user.id, db)

    persons = [
        PersonResponse(
            id=p.id,
            name=p.name,
            photo_count=len(p.photos),
        )
        for p in project.persons
    ]

    return ProjectDetailResponse(
        **ProjectResponse.model_validate(project).model_dump(),
        persons=persons,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project and all associated data (cascade)."""
    project = await _get_user_project(project_id, current_user.id, db)
    await db.delete(project)
    await db.flush()


# ── Photo Endpoints ──────────────────────────────────────


@router.post(
    "/{project_id}/photos",
    status_code=status.HTTP_201_CREATED,
    response_model=PhotoUploadResponse,
)
async def upload_photos(
    project_id: uuid.UUID,
    photos: list[UploadFile],
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoUploadResponse:
    """Upload photos for a project. Filenames must follow <person>_<seq>.<ext> convention."""
    project = await _get_user_project(project_id, current_user.id, db)

    uploaded_photos: list[Photo] = []
    persons_created: set[str] = set()

    # Build a map of existing persons for this project
    existing_persons: dict[str, Person] = {p.name: p for p in project.persons}

    for file in photos:
        if file.filename is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File missing filename",
            )

        # Validate file size and MIME type
        try:
            validate_file(file)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Parse filename
        try:
            person_name, seq_num = parse_filename(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Get or create person
        if person_name not in existing_persons:
            person = Person(
                project_id=project.id,
                name=person_name,
            )
            db.add(person)
            await db.flush()
            existing_persons[person_name] = person
            persons_created.add(person_name)
        else:
            person = existing_persons[person_name]

        # Save file to disk
        file_path = await save_photo_file(
            file,
            user_id=str(current_user.id),
            project_id=str(project.id),
            filename=file.filename,
        )

        # Create photo record
        photo = Photo(
            person_id=person.id,
            original_filename=file.filename,
            sequence_number=seq_num,
            file_path=file_path,
            file_size=file.size or 0,
            mime_type=file.content_type or "application/octet-stream",
        )
        db.add(photo)
        await db.flush()
        uploaded_photos.append(photo)

    return PhotoUploadResponse(
        uploaded=len(uploaded_photos),
        persons_created=sorted(persons_created),
        photos=[PhotoResponse.model_validate(p) for p in uploaded_photos],
    )


@router.get("/{project_id}/photos", response_model=PhotoGroupResponse)
async def list_photos(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoGroupResponse:
    """List photos grouped by person."""
    project = await _get_user_project(project_id, current_user.id, db)

    groups = []
    for person in project.persons:
        groups.append({
            "person": PersonResponse(
                id=person.id,
                name=person.name,
                photo_count=len(person.photos),
            ),
            "photos": [PhotoResponse.model_validate(ph) for ph in person.photos],
        })

    return PhotoGroupResponse(persons=groups)


@router.delete(
    "/{project_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_photo(
    project_id: uuid.UUID,
    photo_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a specific photo."""
    # Verify project ownership
    project = await _get_user_project(project_id, current_user.id, db)

    # Find the photo within this project's persons
    result = await db.execute(
        select(Photo)
        .join(Person)
        .where(
            Photo.id == photo_id,
            Person.project_id == project.id,
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    await db.delete(photo)
    await db.flush()
