
-----------------------------------------------------------
-- Tabla: role
-----------------------------------------------------------
CREATE TABLE role (
    id SERIAL,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    CONSTRAINT pk_role PRIMARY KEY (id)
);

-----------------------------------------------------------
-- Tabla: user
-----------------------------------------------------------
CREATE TABLE "user" (
    id SERIAL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    mother_last_name VARCHAR(50),
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    registration_date DATE,
    is_internal BOOLEAN DEFAULT FALSE,
    role_id INTEGER NOT NULL,
    CONSTRAINT pk_user PRIMARY KEY (id),
    CONSTRAINT fk_user_role FOREIGN KEY (role_id)
        REFERENCES role (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- Tabla: program
-----------------------------------------------------------
CREATE TABLE program (
    id SERIAL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    coordinator_id INTEGER NOT NULL,
    CONSTRAINT pk_program PRIMARY KEY (id),
    CONSTRAINT fk_program_user FOREIGN KEY (coordinator_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- Tabla: step
-----------------------------------------------------------
CREATE TABLE step (
    id SERIAL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    program_id INTEGER NOT NULL,
    CONSTRAINT pk_step PRIMARY KEY (id),
    CONSTRAINT fk_step_program FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- Tabla: submission
-----------------------------------------------------------
CREATE TABLE submission (
    id SERIAL,
    file_path TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    upload_date DATE,
    review_date DATE,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    CONSTRAINT pk_submission PRIMARY KEY (id),
    CONSTRAINT fk_submission_user FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_submission_program FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_submission_step FOREIGN KEY (step_id)
        REFERENCES step (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- Tabla: archive
-----------------------------------------------------------
CREATE TABLE archive (
    id SERIAL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_downloadable BOOLEAN DEFAULT FALSE,
    file_path TEXT NOT NULL,
    submission_id INTEGER NOT NULL,
    CONSTRAINT pk_archive PRIMARY KEY (id),
    CONSTRAINT fk_archive_submission FOREIGN KEY (submission_id)
        REFERENCES submission (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
