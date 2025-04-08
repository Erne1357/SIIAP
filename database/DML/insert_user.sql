INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email, registration_date, is_internal, role_id)
VALUES (
    'Admin', 
    'User', 
    'Test', 
    'admin', 
    'pbkdf2:sha256:260000$Nf1JiGqaYUMvMS4Z$27e6a6757f951a46f54efbd5d4154cdd8b1d65b087278f7411d2257fdaab134a', 
    'admin@test.com', 
    CURRENT_TIMESTAMP, 
    false, 
    1
);