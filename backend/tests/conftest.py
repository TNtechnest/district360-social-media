"""Pytest fixtures for the District360 backend test suite.

Test database: uses the ``TestingConfig`` local SQLite default unless
``TEST_DATABASE_URL`` points at an explicit database.  The schema is created
fresh for every test session and torn down afterward, so tests are isolated
from production data.
"""
import pytest
from app import create_app
from app.extensions import db as _db
from app.models import District, Permission, Role, User, Department


# ---------------------------------------------------------------------------
# App / DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def app():
    """Create the Flask application configured for testing."""
    import os
    os.environ.setdefault(
        'TEST_DATABASE_URL',
        'sqlite:///district360_test.db'
    )
    application = create_app('testing')
    application.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        # Override to dev DB — test isolation is via transaction rollback
        'SQLALCHEMY_DATABASE_URI': os.environ['TEST_DATABASE_URL'],
    })
    return application


@pytest.fixture(scope='session')
def db(app):
    """Expose the database extension for tests."""
    with app.app_context():
        yield _db


@pytest.fixture(autouse=True)
def db_session(db, app):
    """Create a clean schema for every test."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        original_flush = db.session.flush
        flushing = False

        def flush_and_commit(*args, **kwargs):
            nonlocal flushing
            result = original_flush(*args, **kwargs)
            if not flushing:
                flushing = True
                try:
                    db.session.commit()
                finally:
                    flushing = False
            return result

        db.session.flush = flush_and_commit
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def district(db_session):
    """A minimal active district (tenant) — get existing or create."""
    import uuid as _uuid
    slug = f'test-district-{_uuid.uuid4().hex[:8]}'
    d = District(
        name='Test District',
        slug=slug,
        region='Test Region',
        status='active',
        config={},
    )
    db_session.add(d)
    db_session.flush()
    return d


@pytest.fixture
def permission_user_read(db_session):
    """The user:read permission — get existing or create."""
    p = Permission.query.filter_by(resource='user', action='read').first()
    if not p:
        p = Permission(resource='user', action='read', description='Read users')
        db_session.add(p)
        db_session.flush()
    return p


@pytest.fixture
def admin_role(db_session, district, permission_user_read):
    """A district_admin role with user:read permission — get existing or create."""
    role = Role.query.filter_by(district_id=district.id, name='district_admin').first()
    if not role:
        role = Role(
            district_id=district.id,
            name='district_admin',
            description='District administrator',
            is_system=False,
        )
        db_session.add(role)
        db_session.flush()
    if permission_user_read not in role.permissions:
        role.permissions.append(permission_user_read)
        db_session.flush()
    return role


@pytest.fixture
def admin_user(db_session, district, admin_role):
    """An active admin user with the district_admin role."""
    from app.extensions import bcrypt
    user = User(
        district_id=district.id,
        email='admin@test.example',
        full_name='Admin User',
        password_hash=bcrypt.generate_password_hash('Admin1234').decode('utf-8'),
        auth_provider='local',
        status='active',
    )
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_headers(client, admin_user, district):
    """JWT Authorization headers for the admin_user fixture."""
    response = client.post('/api/v1/auth/login', json={
        'district_id': district.id,
        'email': 'admin@test.example',
        'password': 'Admin1234',
    })
    token = response.get_json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}
