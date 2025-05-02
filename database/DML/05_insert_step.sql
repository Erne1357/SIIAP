-- insert_step.sql
-- Pasos por fase (admission, permanence, conclusion)
INSERT INTO step (id, name, description, phase_id) VALUES
(1, 'Documentos generales', 'Requisitos comunes de admisión', 1),
(2, 'Documentos específicos MII', 'Requisitos específicos del programa MII', 1),
(3, 'Documentos específicos MANI', 'Requisitos específicos del programa MANI', 1),
(4, 'Documentos específicos MIA', 'Requisitos específicos del programa MIA', 1),
(5, 'Documentos específicos DCI', 'Requisitos específicos del programa DCI', 1),
(6, 'Exámenes Maestría', 'Comprobantes y exámenes para programas de maestría', 1),
(7, 'Exámenes Doctorado', 'Comprobantes y exámenes para doctorado', 1),
(8, 'Entrevista', 'Entrevista con Comité de Admisión', 1),
(9, 'Seguimiento semestral', 'Actualización de avance académico', 2),
(10, 'Movilidad', 'Registro y autorización de movilidad', 2),
(11, 'Solicitud de egreso', 'Solicitud formal de conclusión del programa', 3),
(12, 'Trabajo/Protocolo', 'Entrega de tesis o trabajo recepcional', 3),
(13, 'Defensa', 'Defensa de tesis ante sínodo', 3),
(14, 'Encuesta fin de programa', 'Encuesta de satisfacción al egreso', 3);
