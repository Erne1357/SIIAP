-- insert_program_step.sql
INSERT INTO program_step (sequence, program_id, step_id) VALUES
--Fase de admisión
(0, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 8),
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 1),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 2),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 3),
(4, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 6),
--Fase de permanencia
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 9),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 10),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 11),
(4, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 12),
--Fase de conclusión
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 13),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 14),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Industrial'), 16),

------------------------------------------------------------------------------------------------

--Fase de admisión
(0, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 8),
(1, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 1),
(2, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 2),
(3, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 4),
(4, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 6),
--Fase de permanencia
(1, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 9),
(2, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 10),
(3, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 11),
(4, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 12),
--Fase de conclusión
(1, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 13),
(2, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 14),
(3, (SELECT id FROM program WHERE name='Maestría en Administración de Negocios Internacionales'), 16),

--------------------------------------------------------------------------------------------------------------

--Fase de admisión
(0, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 8),
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 1),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 2),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 3),
(4, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 6),
--Fase de permanencia
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 9),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 10),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 11),
(4, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 12),
--Fase de conclusión
(1, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 13),
(2, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 14),
(3, (SELECT id FROM program WHERE name='Maestría en Ingeniería Administrativa'), 16),

-------------------------------------------------------------------------------------------

--Fase de admisión
(0, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 8),
(1, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 1),
(2, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 2),
(3, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 5),
(4, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 7),
--Fase de permanencia
(1, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 9),
(2, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 10),
(3, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 11),
(4, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 12),
--Fase de conclusión
(1, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 13),
(2, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 15),
(3, (SELECT id FROM program WHERE name='Doctorado en Ciencias de la Ingeniería'), 16);
