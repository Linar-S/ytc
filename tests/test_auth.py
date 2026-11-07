"""Authentication endpoint tests against an in-memory async database."""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an auth client backed by isolated in-memory SQLite."""

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db() -> AsyncIterator:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as test_client:
                yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def register(
    client: AsyncClient,
    email: str = "alice@example.com",
    username: str = "alice",
    password: str = PASSWORD,
):
    """Register a user through the public endpoint."""

    return await client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )


async def login(
    client: AsyncClient,
    email: str = "alice@example.com",
    password: str = PASSWORD,
):
    """Log in through the public endpoint."""

    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_register_first_user_is_admin_and_second_is_user(
    client: AsyncClient,
) -> None:
    first = await register(client)
    assert first.status_code == 201
    assert first.json()["role"] == "admin"
    assert "password" not in first.json()

    second = await register(client, email="bob@example.com", username="bob")
    assert second.status_code == 201
    assert second.json()["role"] == "user"


async def test_register_duplicate_email_returns_400(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201

    duplicate = await register(client, username="alicetwo")
    assert duplicate.status_code == 400
    assert "already" in duplicate.json()["detail"].lower()


async def test_register_weak_password_returns_422(client: AsyncClient) -> None:
    response = await register(client, password="short")
    assert response.status_code == 422


async def test_login_success_and_invalid_password(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201

    response = await login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60

    wrong_password = await login(client, password="wrong-password")
    assert wrong_password.status_code == 401


async def test_protected_endpoint_requires_access_token(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201
    login_response = await login(client)
    access_token = login_response.json()["access_token"]

    unauthorized = await client.get("/auth/me")
    assert unauthorized.status_code == 401

    authorized = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["email"] == "alice@example.com"


async def test_refresh_rotation_invalidates_old_token(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201
    tokens = (await login(client)).json()

    refreshed = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reused = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401

    second_tokens = (await login(client)).json()
    all_sessions_logged_out = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {second_tokens['access_token']}"},
    )
    assert all_sessions_logged_out.status_code == 200
    reused_after_all_sessions_logout = await client.post(
        "/auth/refresh",
        json={"refresh_token": second_tokens["refresh_token"]},
    )
    assert reused_after_all_sessions_logout.status_code == 401

    authorized = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert authorized.status_code == 200


async def test_require_role_admin_rejects_user(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201
    assert (await register(client, email="bob@example.com", username="bob")).status_code == 201

    user_tokens = (await login(client, email="bob@example.com")).json()
    forbidden = await client.get(
        "/auth/admin-only",
        headers={"Authorization": f"Bearer {user_tokens['access_token']}"},
    )
    assert forbidden.status_code == 403

    admin_tokens = (await login(client)).json()
    allowed = await client.get(
        "/auth/admin-only",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert allowed.status_code == 200


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    assert (await register(client)).status_code == 201
    tokens = (await login(client)).json()

    logged_out = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logged_out.status_code == 200

    reused = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401

    second_tokens = (await login(client)).json()
    all_sessions_logged_out = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {second_tokens['access_token']}"},
    )
    assert all_sessions_logged_out.status_code == 200
    reused_after_all_sessions_logout = await client.post(
        "/auth/refresh",
        json={"refresh_token": second_tokens["refresh_token"]},
    )
    assert reused_after_all_sessions_logout.status_code == 401
