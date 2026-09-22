from fastapi import FastAPI, HTTPException, Query, Path, Depends
from datetime import datetime
from typing import Literal, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from database import get_db
import models, schemas, auth
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI()

@app.post("/auth/register", response_model=schemas.UserResponse, status_code=201)
async def register(user: schemas.UserRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(models.User).where(models.User.email == user.email)
    result = await db.execute(stmt)
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    hashed_password = auth.hash_password(user.password)
    created_time = datetime.now(timezone.utc)
    new_user = models.User(
        email = user.email,
        password_hash = hashed_password,
        created_at = created_time
        )

    try:
        db.add(new_user)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    await db.refresh(new_user)
    return new_user

@app.post("/auth/token", response_model=schemas.Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
    ):
    stmt = select(models.User).where(models.User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/tasks", response_model=schemas.TaskResponse, status_code=201)
async def create_task(
    task: schemas.TaskCreate,
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    db: AsyncSession = Depends(get_db)
    ):
    created_time = datetime.now(timezone.utc)
    new_task = models.Task(
        title = task.title,
        description = task.description,
        completed = False,
        priority = task.priority,
        created_at = created_time,
        user_id = current_user.id
        )

    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

@app.get("/tasks", response_model=schemas.TaskListResponse)
async def get_tasks(
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    completed: bool | None = Query(default=None),
    priority: int | None = Query(default=None, ge = 1, le = 100),
    limit: int = Query(default = 10, ge = 1, le = 100),
    offset: int = Query(default = 0, ge = 0),
    sort_by: Literal[
        "id",
        "title",
        "priority",
        "completed",
        "created_at"
        ] = Query(default = "id"),
    sort_order: Literal["asc", "desc"] = Query(default = "asc"),
    db: AsyncSession = Depends(get_db)
    ):
    stmt = select(models.Task).where(models.Task.user_id == current_user.id)

    if completed is not None:
        stmt = stmt.where(models.Task.completed == completed)
    if priority is not None:
        stmt = stmt.where(models.Task.priority == priority)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    column = getattr(models.Task, sort_by)
    if sort_order == "asc":
        stmt = stmt.order_by(column.asc())
    elif sort_order == "desc":
        stmt = stmt.order_by(column.desc())

    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return {
        "tasks": tasks,
        "total": total,
        "offset": offset,
        "limit": limit
        }

@app.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    task_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db)
    ):
    stmt = select(models.Task).where(models.Task.id == task_id)
    stmt = stmt.where(models.Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404,detail="Task not found.")
    return task

@app.patch("/tasks/{task_id}", response_model=schemas.TaskResponse)
async def update_task(
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    task_update: schemas.TaskUpdate,
    task_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db)
    ):
    stmt = select(models.Task).where(models.Task.id == task_id)
    stmt = stmt.where(models.Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code = 404, detail = "Task not found.")

    task_update = task_update.model_dump(exclude_unset=True)
    for field, value in task_update.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)

    return task

@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    task_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db)
    ):
    stmt = select(models.Task).where(models.Task.id == task_id)
    stmt = stmt.where(models.Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code = 404, detail = "Task not found.")

    await db.delete(task)
    await db.commit()
    return

@app.delete("/users/me", status_code=204)
async def delete_user(
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    db: AsyncSession = Depends(get_db)
    ):
    await db.delete(current_user)
    await db.commit()
    return
