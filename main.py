
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import asyncpg
import bcrypt
import jwt
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator


DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Некорректное имя")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value.encode("utf-8")) > 72 or "\x00" in value:
            raise ValueError("Недопустимый пароль")
        return value


class LoginRequest(BaseModel):
    login: str
    password: str


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Некорректное имя")
        return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)

    async with app.state.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

    yield
    await app.state.pool.close()


app = FastAPI(
    title="Lab 14 — Authentication Microservice",
    description="REST API для регистрации и авторизации пользователей",
    version="1.0.0",
    lifespan=lifespan
)


def create_token(user_id: str):
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Требуется токен Bearer"
        )

    token = authorization[7:]

    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        user_id = payload["sub"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(
            status_code=401,
            detail="Недействительный или просроченный токен"
        )

    async with app.state.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, name, email FROM users WHERE id = $1",
            user_id
        )

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return dict(user)


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    email = str(data.email).lower()

    password_hash = bcrypt.hashpw(
        data.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    user_id = str(uuid.uuid4())

    try:
        async with app.state.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, name, email, password_hash)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, data.name, email, password_hash
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким email уже существует"
        )

    return {
        "user": {"id": user_id, "name": data.name, "email": email},
        "access_token": create_token(user_id),
        "token_type": "bearer"
    }


@app.post("/api/auth/login")
async def login(data: LoginRequest):
    if "\x00" in data.login:
        raise HTTPException(status_code=422, detail="Некорректный логин")

    async with app.state.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1 OR id = $1",
            data.login.lower()
        )

    if not user or not bcrypt.checkpw(
        data.password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль"
        )

    return {
        "access_token": create_token(user["id"]),
        "token_type": "bearer"
    }


@app.get("/api/auth/me")
async def get_profile(authorization: str | None = Header(default=None)):
    user = await get_current_user(authorization)
    return {"user": user}


@app.patch("/api/user/profile")
async def update_profile(
    data: ProfileUpdate,
    authorization: str | None = Header(default=None)
):
    user = await get_current_user(authorization)

    async with app.state.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET name = $1 WHERE id = $2",
            data.name, user["id"]
        )

    user["name"] = data.name
    return {"user": user}
