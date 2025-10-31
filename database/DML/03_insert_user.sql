--Usuario de prueba con el máximo de privilegios
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id, avatar)
VALUES (
    'Admin', 
    'User', 
    'Test', 
    'admin', 
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
    'admin@test.com', 
    CURRENT_TIMESTAMP, 
    false, 
    4,
    'profile.jpg'
);
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id)
VALUES (
    'Jorge Adolfo', 
    'Pinto', 
    'Santos', 
    'jpinto', 
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
    'jefatura_depi@cdjuarez.tecnm.mx', 
    CURRENT_TIMESTAMP, 
    false, 
    4
);

--Usuario de prueba con el mínimo de privilegios
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id)
VALUES (
    'Ernesto', 
    'Villarreal', 
    'Ibarra', 
    'Erne1357', 
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
    'Erne1357@test.com', 
    CURRENT_TIMESTAMP, 
    false, 
    1
);

--Insertar usuarios de servicio social
INSERT INTO "user" (first_name, last_name, username, password, email, registration_date, is_internal, role_id)
VALUES (
    'Servicio', 
    'Social', 
    'Servicio', 
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
    'servicio@test.com', 
    CURRENT_TIMESTAMP, 
    false, 
    2
);

-- Insertar usuarios de coordinadores de programa
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id) VALUES
('Germán', 'Quiroz', 'Merino', 'gquiroz',
 'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
 'coordinacion_dci@cdjuarez.tecnm.mx', CURRENT_TIMESTAMP, TRUE, 3),  -- Coordinador de DCI
('Israel Emmanuel', 'Zapata', 'de Santiago', 'izapata',
 'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
 'coordinacion_mii@cdjuarez.tecnm.mx', CURRENT_TIMESTAMP, TRUE, 3),  -- Coordinador de MII 
('Manuel Alejandro', 'Barajas', 'Bustillos', 'mbarajas', 
'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
'coordinacion_mani@cdjuarez.tecnm.mx', CURRENT_TIMESTAMP, TRUE, 3) ; -- Coordinador de MIA y MANI
