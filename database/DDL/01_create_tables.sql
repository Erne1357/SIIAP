-- 1) role -------------------------------------------------
CREATE TABLE role (
    id  SERIAL PRIMARY KEY,
    name VARCHAR(50)  NOT NULL,
    description TEXT
);

-- 2) "user" ----------------------------------------------
CREATE TABLE "user" (
    id               SERIAL PRIMARY KEY,
    first_name       VARCHAR(50)  NOT NULL,
    last_name        VARCHAR(50)  NOT NULL,
    mother_last_name VARCHAR(50)  ,
    username         VARCHAR(50)  NOT NULL UNIQUE,
    password         VARCHAR(255) NOT NULL,
    email            VARCHAR(100) NOT NULL UNIQUE,
    last_login       TIMESTAMP    NOT NULL DEFAULT NOW(),
    is_internal      BOOLEAN      NOT NULL DEFAULT FALSE,
    registration_date TIMESTAMP   NOT NULL DEFAULT NOW(),
    role_id           INTEGER      NOT NULL,
    CONSTRAINT fk_user_role
        FOREIGN KEY (role_id)
        REFERENCES role (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 3) program ---------------------------------------------
CREATE TABLE program (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    description    TEXT,
    coordinator_id INTEGER      NOT NULL,
    slug          VARCHAR(100)  NOT NULL UNIQUE,
    CONSTRAINT fk_program_user
        FOREIGN KEY (coordinator_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 4) phase -----------------------------------------------
CREATE TABLE phase (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT
);

-- 5) step -------------------------------------------------
CREATE TABLE step (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    description TEXT,
    phase_id  INTEGER NOT NULL,
    CONSTRAINT fk_step_phase
        FOREIGN KEY (phase_id)
        REFERENCES phase (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 6) program_step (puente) -------------------------------
CREATE TABLE program_step (
    id SERIAL PRIMARY KEY,
    sequence     INTEGER NOT NULL,
    program_id   INTEGER NOT NULL,
    step_id      INTEGER NOT NULL,
    CONSTRAINT fk_program_step_program
        FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_program_step_step
        FOREIGN KEY (step_id)
        REFERENCES step (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 7) archive ---------------------------------------------
CREATE TABLE archive (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    file_path       TEXT NOT NULL,
    is_downloadable BOOLEAN NOT NULL DEFAULT FALSE,
    step_id         INTEGER NOT NULL,
    CONSTRAINT fk_archive_step
        FOREIGN KEY (step_id)
        REFERENCES step (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 8) submission ------------------------------------------
CREATE TABLE submission (
    id              SERIAL PRIMARY KEY,
    file_path       TEXT        NOT NULL,
    status          VARCHAR(50) NOT NULL,
    upload_date     TIMESTAMP   NOT NULL DEFAULT NOW(),
    review_date     TIMESTAMP,
    user_id         INTEGER     NOT NULL,
    archive_id      INTEGER     NOT NULL,
    program_step_id INTEGER     NOT NULL,
    CONSTRAINT fk_submission_user
        FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_submission_archive
        FOREIGN KEY (archive_id)
        REFERENCES archive (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_submission_program_step
        FOREIGN KEY (program_step_id)
        REFERENCES program_step (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 9) user_program ----------------------------------------
CREATE TABLE user_program (
    id               SERIAL PRIMARY KEY,
    enrollment_date  TIMESTAMP NOT NULL DEFAULT NOW(),
    current_semester INTEGER,
    status           VARCHAR(50) NOT NULL DEFAULT 'active',
    user_id          INTEGER NOT NULL,
    program_id       INTEGER NOT NULL,
    CONSTRAINT fk_user_program_user
        FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_user_program_program
        FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 10) log ------------------------------------------------
CREATE TABLE log (
    id          SERIAL PRIMARY KEY,
    action      VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    user_id     INTEGER     NOT NULL,
    CONSTRAINT fk_log_user
        FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
