
# Lab 14 — Authentication Microservice

Микросервис авторизации пользователей с REST API.

## Технологии

- Python 3.12
- FastAPI
- PostgreSQL 16
- Docker
- Docker Compose
- Multi-stage Dockerfile
- JWT и bcrypt

## REST API

| Метод | Маршрут | Назначение |
|---|---|---|
| POST | /api/auth/register | Регистрация |
| POST | /api/auth/login | Авторизация |
| GET | /api/auth/me | Получение профиля |
| PATCH | /api/user/profile | Изменение профиля |

## Запуск

1. Клонировать репозиторий.
2. Создать файл `.env` по образцу `.env.example`.
3. Указать значения POSTGRES_PASSWORD и JWT_SECRET_KEY.
4. Выполнить:

```bash
docker compose up -d --build
```

5. Открыть Swagger:

http://127.0.0.1:8014/docs

## Проверка контейнеров

```bash
docker compose ps
```

## Обработка ошибок

- 401 — ошибка авторизации.
- 409 — пользователь уже существует.
- 422 — ошибка валидации данных.

## Остановка

```bash
docker compose down
```

Данные PostgreSQL сохраняются в именованном Docker-томе.
