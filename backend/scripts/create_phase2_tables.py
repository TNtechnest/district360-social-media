"""Direct DDL: create social_comment and comment_analysis tables."""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app('development')
with app.app_context():

    # Check if social_comment already exists
    result = db.session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='social_comment'"
    ))
    if result.fetchone():
        print('social_comment: already exists')
    else:
        db.session.execute(text("""
            CREATE TABLE social_comment (
                id                  VARCHAR(36) PRIMARY KEY,
                district_id         VARCHAR(36) NOT NULL REFERENCES district(id) ON DELETE CASCADE,
                post_id             VARCHAR(36) NOT NULL REFERENCES social_post(id) ON DELETE CASCADE,
                parent_comment_id   VARCHAR(36) REFERENCES social_comment(id) ON DELETE CASCADE,
                platform            VARCHAR(30) NOT NULL,
                platform_comment_id VARCHAR(255) NOT NULL,
                author_platform_id  VARCHAR(255),
                author_name         VARCHAR(255),
                author_username     VARCHAR(255),
                author_profile_url  TEXT,
                text                TEXT NOT NULL,
                platform_created_at VARCHAR(50),
                likes               INTEGER NOT NULL DEFAULT 0,
                reply_count         INTEGER NOT NULL DEFAULT 0,
                moderation_status   VARCHAR(20) NOT NULL DEFAULT 'visible',
                is_replied          BOOLEAN NOT NULL DEFAULT false,
                reply_text          TEXT,
                reply_platform_id   VARCHAR(255),
                replied_at          VARCHAR(50),
                replied_by_id       VARCHAR(36) REFERENCES "user"(id) ON DELETE SET NULL,
                language            VARCHAR(20) NOT NULL DEFAULT 'unknown',
                sentiment           VARCHAR(20),
                sentiment_score     FLOAT,
                is_complaint        BOOLEAN NOT NULL DEFAULT false,
                is_emergency        BOOLEAN NOT NULL DEFAULT false,
                is_spam             BOOLEAN NOT NULL DEFAULT false,
                suggested_reply     TEXT,
                ai_status           VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT uix_social_comment_post_platform_comment
                    UNIQUE (post_id, platform_comment_id)
            )
        """))
        # Indexes
        db.session.execute(text('CREATE INDEX ix_social_comment_district_id    ON social_comment(district_id)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_post_id         ON social_comment(post_id)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_parent          ON social_comment(parent_comment_id)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_platform        ON social_comment(platform)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_moderation      ON social_comment(moderation_status)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_sentiment       ON social_comment(sentiment)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_is_complaint    ON social_comment(is_complaint)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_is_emergency    ON social_comment(is_emergency)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_is_spam         ON social_comment(is_spam)'))
        db.session.execute(text('CREATE INDEX ix_social_comment_ai_status       ON social_comment(ai_status)'))
        db.session.commit()
        print('social_comment: CREATED')

    # comment_analysis
    result2 = db.session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='comment_analysis'"
    ))
    if result2.fetchone():
        print('comment_analysis: already exists')
    else:
        db.session.execute(text("""
            CREATE TABLE comment_analysis (
                id                   VARCHAR(36) PRIMARY KEY,
                district_id          VARCHAR(36) NOT NULL REFERENCES district(id) ON DELETE CASCADE,
                comment_id           VARCHAR(36) NOT NULL UNIQUE REFERENCES social_comment(id) ON DELETE CASCADE,
                language             VARCHAR(20) NOT NULL DEFAULT 'unknown',
                sentiment_label      VARCHAR(20),
                sentiment_score      FLOAT,
                is_complaint         BOOLEAN NOT NULL DEFAULT false,
                complaint_confidence FLOAT NOT NULL DEFAULT 0,
                complaint_keywords   JSONB NOT NULL DEFAULT '[]',
                is_emergency         BOOLEAN NOT NULL DEFAULT false,
                emergency_confidence FLOAT NOT NULL DEFAULT 0,
                emergency_keywords   JSONB NOT NULL DEFAULT '[]',
                is_spam              BOOLEAN NOT NULL DEFAULT false,
                spam_confidence      FLOAT NOT NULL DEFAULT 0,
                spam_reasons         JSONB NOT NULL DEFAULT '[]',
                trend_tags           JSONB NOT NULL DEFAULT '[]',
                top_topic            VARCHAR(100),
                suggested_reply      TEXT,
                reply_category       VARCHAR(30),
                status               VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message        TEXT,
                raw_result           JSONB NOT NULL DEFAULT '{}',
                processing_ms        INTEGER NOT NULL DEFAULT 0,
                created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_district_id   ON comment_analysis(district_id)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_comment_id    ON comment_analysis(comment_id)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_sentiment      ON comment_analysis(sentiment_label)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_is_complaint   ON comment_analysis(is_complaint)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_is_emergency   ON comment_analysis(is_emergency)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_is_spam        ON comment_analysis(is_spam)'))
        db.session.execute(text('CREATE INDEX ix_comment_analysis_status         ON comment_analysis(status)'))
        db.session.commit()
        print('comment_analysis: CREATED')

    print('Done.')
