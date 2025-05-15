-- insert_step.sql
-- Pasos por fase (admission, permanence, conclusion)
INSERT INTO step (id, name, description, phase_id) VALUES
(1, 'Documentos generales', 'Requisitos comunes de admisión', 1),
(2, 'Requisitos de Maestrías', 'Requisitos específicos de maestrías', 1),
(3, 'Documentos específicos MII/MIA', 'Requisitos específicos del programa MII y MIA', 1),
(4, 'Documentos específicos MANI', 'Requisitos específicos del programa MANI', 1),
(5, 'Documentos específicos DCI', 'Requisitos específicos del programa DCI', 1),
(6, 'Entrevista', 'Entrevista con Comité de Admisión', 1),
(7, 'Defensa de protocolo ', 'Defensa de protocolo/propuesta de investigación con Comité de admisión',1),
(8, 'Temarios de examen', 'Temarios de examenes de admisión',1),
--Fase de permanencia
(9,'Permanencia' , 'Documentos de permanencia', 2),
(10,'Movilidad', 'Documentos de movilidad', 2),
(11, 'Seguimiento semestral', 'Actualización de avance académico', 2),
(12, 'Becarios Conahcyt', 'Registro y autorización de movilidad', 2),
--Fase de conclusión
(13, 'Requisitos generales', 'Solicitud formal de conclusión del programa', 3),
(14, 'Requisitos de maestrías', 'Entrega de tesis o trabajo recepcional', 3),
(15, 'Requisitos de Doctorados', 'Defensa de tesis ante sínodo', 3),
(16, 'Encuesta fin de programa', 'Encuesta de satisfacción al egreso', 3);
