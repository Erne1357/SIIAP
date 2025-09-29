-- insert_step.sql
-- Pasos por fase (admission, permanence, conclusion)
INSERT INTO step (id, name, description, phase_id) VALUES
(1, 'Documentos Generales', 'Requisitos comunes de admisión', 1),
(2, 'Requisitos de Maestrías', 'Requisitos específicos de maestrías', 1),
(3, 'Documentos Específicos MII/MIA', 'Requisitos específicos del programa MII y MIA', 1),
(4, 'Documentos Específicos MANI', 'Requisitos específicos del programa MANI', 1),
(5, 'Documentos Específicos DCI', 'Requisitos específicos del programa DCI', 1),
(6, 'Entrevista', 'Entrevista con Comité de Admisión', 1),
(7, 'Defensa de Protocolo ', 'Defensa de protocolo/propuesta de investigación con Comité de admisión',1),
(8, 'Temarios de Examen', 'Temarios de examenes de admisión',1),
--Fase de permanencia
(9,'Permanencia' , 'Documentos de permanencia', 2),
(10,'Movilidad', 'Documentos de movilidad', 2),
(11, 'Seguimiento Semestral', 'Actualización de avance académico', 2),
(12, 'Becarios Conacyt', 'Registro y autorización de movilidad', 2),
--Fase de conclusión
(13, 'Requisitos Generales', 'Solicitud formal de conclusión del programa', 3),
(14, 'Requisitos de Maestrías', 'Entrega de tesis o trabajo recepcional', 3),
(15, 'Requisitos de Doctorados', 'Defensa de tesis ante sínodo', 3),
(16, 'Encuesta Fin de Programa', 'Encuesta de satisfacción al egreso', 3);
