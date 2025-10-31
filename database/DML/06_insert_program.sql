-- insert_program.sql
-- Programas de posgrado activos
INSERT INTO program (name, description, coordinator_id, slug) VALUES
('Maestría en Ingeniería Industrial',
 'Programa de maestría orientado a la optimización de sistemas industriales y productividad',
 (Select id from "user" where username = 'izapata'), 'MII'),
('Maestría en Administración de Negocios Internacionales',
 'Programa de maestría enfocado en la gestión y estrategia de negocios globales',
 (Select id from "user" where username = 'mbarajas'), 'MANI'),
('Maestría en Ingeniería Administrativa',
 'Programa de maestría que integra ingeniería con administración para la mejora de procesos',
 (Select id from "user" where username = 'mbarajas'), 'MIA'),
('Doctorado en Ciencias de la Ingeniería',
 'Programa doctoral de investigación avanzada en ciencias e ingeniería',
 (Select id from "user" where username = 'gquiroz'), 'DCI');
