-----------------------------------------------------------
-- 1) Tabla: role
-----------------------------------------------------------
CREATE TABLE role (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT
);

-----------------------------------------------------------
-- 2) Tabla: user
-----------------------------------------------------------
-- Nota: Usamos "user" entre comillas debido a que es palabra reservada.
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    mother_last_name VARCHAR(50),
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    registration_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP NOT NULL DEFAULT NOW(),
    is_internal BOOLEAN DEFAULT FALSE,
    role_id INTEGER NOT NULL,
    CONSTRAINT fk_user_role FOREIGN KEY (role_id)
        REFERENCES role (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 3) Tabla: program
-----------------------------------------------------------
CREATE TABLE program (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    coordinator_id INTEGER NOT NULL,
    CONSTRAINT fk_program_user FOREIGN KEY (coordinator_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 4) Tabla: phase
-----------------------------------------------------------
CREATE TABLE phase (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT
);

-----------------------------------------------------------
-- 5) Tabla: step
-----------------------------------------------------------
CREATE TABLE step (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    phase_id INTEGER NOT NULL,
    CONSTRAINT fk_step_phase FOREIGN KEY (phase_id)
        REFERENCES phase (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 6) Tabla: program_step (Tabla puente entre program y step)
-----------------------------------------------------------
CREATE TABLE program_step (
    id SERIAL PRIMARY KEY,
    program_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    CONSTRAINT fk_program_step_program FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_program_step_step FOREIGN KEY (step_id)
        REFERENCES step (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 7) Tabla: submission
-----------------------------------------------------------
CREATE TABLE submission (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    upload_date TIMESTAMP DEFAULT NOW(),
    review_date TIMESTAMP,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
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
-- 8) Tabla: archive
-----------------------------------------------------------
CREATE TABLE archive (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_downloadable BOOLEAN DEFAULT FALSE,
    file_path TEXT NOT NULL,
    submission_id INTEGER NOT NULL,
    CONSTRAINT fk_archive_submission FOREIGN KEY (submission_id)
        REFERENCES submission (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 9) Tabla: user_program
-----------------------------------------------------------
CREATE TABLE user_program (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    enrollment_date TIMESTAMP DEFAULT NOW(),
    current_semester INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    CONSTRAINT fk_user_program_user FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_user_program_program FOREIGN KEY (program_id)
        REFERENCES program (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 10) Tabla: log
-----------------------------------------------------------
CREATE TABLE log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_log_user FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);
