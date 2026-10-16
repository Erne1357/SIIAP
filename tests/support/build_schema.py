"""
Build the SIIAP schema on an EMPTY database from the models, then stamp it at
the Alembic head.

Why not `flask db upgrade`: the first migration (220e09fdfab8) alters tables
that were created by the hand-applied DDL in database/, which never enters git.
The migration chain therefore cannot rebuild a database from zero, and CI / E2E
build it from the models instead — the same approach the sibling ITCJ project
uses. Real migrations run on the production server, behind a pg_dump.

Usage: python -m tests.support.build_schema   (reads DATABASE_URL)
"""

import sys

from flask_migrate import stamp


def main() -> int:
    from app import create_app, db
    import app.models  # noqa: F401  (register every table)

    application = create_app()
    with application.app_context():
        db.create_all()
        stamp(revision='head')
        print(f'schema: {len(db.metadata.tables)} tablas creadas y sellado en head')
    return 0


if __name__ == '__main__':
    sys.exit(main())
