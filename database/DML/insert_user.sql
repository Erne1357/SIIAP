INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id)
VALUES (
    'Admin', 
    'User', 
    'Test', 
    'admin', 
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835', 
    'admin@test.com', 
    CURRENT_TIMESTAMP, 
    false, 
    1
);