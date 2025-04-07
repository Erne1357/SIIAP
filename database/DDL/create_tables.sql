-----------------------------------------------------------
-- 1) Tabla: role
-----------------------------------------------------------
CREATE TABLE role (
    id SERIAL,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    CONSTRAINT pk_role PRIMARY KEY (id)
);

-----------------------------------------------------------
-- 2) Tabla: user
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
-- 3) Tabla: program
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
-- 4) Tabla: phase
--    
-----------------------------------------------------------
CREATE TABLE phase (
    id SERIAL,
    name VARCHAR(50) NOT NULL,           
    description TEXT,
    CONSTRAINT pk_phase PRIMARY KEY (id)
);

-----------------------------------------------------------
-- 5) Tabla: step
--   
--    
-----------------------------------------------------------
CREATE TABLE step (
    id SERIAL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    phase_id INTEGER NOT NULL,
    CONSTRAINT pk_step PRIMARY KEY (id),
    CONSTRAINT fk_step_phase FOREIGN KEY (phase_id)
        REFERENCES phase (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-----------------------------------------------------------
-- 6) Tabla: program_step (Tabla puente para la relación muchos a muchos entre program y step)
-----------------------------------------------------------
CREATE TABLE program_step (
    id SERIAL,
    program_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    CONSTRAINT pk_program_step PRIMARY KEY (id),
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
--    
--    
-----------------------------------------------------------
CREATE TABLE submission (
    id SERIAL,
    file_path TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    upload_date DATE,
    review_date DATE,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,  -- El usuario elige a cuál program aplica
    step_id INTEGER NOT NULL,     -- Qué paso está cumpliendo
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
-- 8) Tabla: archive
--    Contiene los archivos individuales relacionados a una submission (si la submission
--    requiere varios documentos). Si usualmente es 1 a 1, puedes usar la misma submission,
--    pero si necesitas múltiples archivos por submission, esta estructura es correcta.
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

-----------------------------------------------------------
-- 9) Tabla: user_program
--    Registra la permanencia del usuario en un programa
--    (semestres, status, etc.)
-----------------------------------------------------------
CREATE TABLE user_program (
    id SERIAL,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    enrollment_date DATE,
    current_semester INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'active', 
        -- Ej. ['active','graduated','dropped'], etc.
    CONSTRAINT pk_user_program PRIMARY KEY (id),
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
--     Bitácora de acciones en el sistema (cambios de estatus,
--     validaciones, etc.)
-----------------------------------------------------------
CREATE TABLE log (
    id SERIAL,
    user_id INTEGER,
    action VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_log PRIMARY KEY (id),
    CONSTRAINT fk_log_user FOREIGN KEY (user_id)
        REFERENCES "user" (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);
