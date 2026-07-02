# Fix Log

## Fix 1

- **Error Found:** `NameError: name 'Permission' is not defined` while loading `app.models.role`.
- **Root Cause:** `Permission.roles = relationship(...)` was assigned at module scope without importing `Permission`, and `Role.users = relationship(...)` used the same fragile pattern.
- **File Modified:** `backend/app/models/role.py`, `backend/app/models/permission.py`, `backend/app/models/user.py`
- **Fix Applied:** Moved `Role.users`, `Role.permissions`, `Permission.roles`, and `User.roles` into their model classes using string model/table references and removed module-level relationship assignment.

## Fix 2

- **Error Found:** `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.`
- **Root Cause:** `ActivityLog` declared a mapped Python attribute named `metadata`, which conflicts with SQLAlchemy Declarative's reserved `metadata` attribute.
- **File Modified:** `backend/app/models/activity_log.py`, `backend/app/services/audit_service.py`
- **Fix Applied:** Renamed the mapped Python attribute to `metadata_` while preserving the database column name `metadata`; updated activity log creation to use `metadata_` and kept serialized API output as `metadata`.

## Fix 3

- **Error Found:** `NameError: name 'relationship' is not defined` while importing `app.models.collected_post`.
- **Root Cause:** `CollectedPost.account` used SQLAlchemy `relationship()` without importing it from `sqlalchemy.orm`.
- **File Modified:** `backend/app/models/collected_post.py`
- **Fix Applied:** Added `relationship` to the SQLAlchemy ORM imports.

## Fix 4

- **Error Found:** `TypeError: Invalid argument(s) 'pool_size','max_overflow','pool_timeout' sent to create_engine()` when using a SQLite `DATABASE_URL`.
- **Root Cause:** PostgreSQL-specific SQLAlchemy pool options were applied unconditionally to every database engine.
- **File Modified:** `backend/app/config.py`
- **Fix Applied:** Added database URI and engine-option helpers so SQLite receives no PostgreSQL pool options while PostgreSQL keeps the existing pooling configuration.

## Fix 5

- **Error Found:** `sqlalchemy.exc.InvalidRequestError: On relationship ServiceRequestCategory.children, 'dynamic' loaders cannot be used with many-to-one/one-to-one relationships and/or uselist=False.`
- **Root Cause:** The self-referential category relationship put `remote_side` on the `children` relationship via `backref`, causing SQLAlchemy to configure it as the scalar parent side.
- **File Modified:** `backend/app/models/service_request.py`
- **Fix Applied:** Replaced the ambiguous `backref` mapping with explicit `parent` and `children` relationships using `back_populates`, keeping `remote_side` on `parent` and `lazy='dynamic'` on `children`.

## Fix 6

- **Error Found:** `RequestsDependencyWarning: urllib3 (2.7.0) or chardet (7.4.3)/charset_normalizer (3.4.7) doesn't match a supported version!`
- **Root Cause:** The virtualenv had unpinned newer transitive dependencies; `requests` checks `chardet` first when installed, and `chardet 7.4.3` is outside its supported runtime range.
- **File Modified:** `backend/requirements.txt`
- **Fix Applied:** Added explicit compatible transitive pins for `chardet`, `urllib3`, and `charset-normalizer` so fresh installs avoid the warning.
