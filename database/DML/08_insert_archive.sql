-- insert_archive.sql
-- === Phase: Admission ===
INSERT INTO archive (name, description, file_path, is_downloadable,is_uploadable, step_id) VALUES
--1
('Currículum Vitae','Currículum Vitae con Documentos Probatorios.',null,FALSE,TRUE,1),
--2
('Cartas de Recomendación','Cartas de Recomendación (2) Dirigidas al Comité de Admisión Firmadas por Especialistas Externos al Plantel.',null,TRUE,TRUE,1),
--3
('Comprobante EXANI III','Comprobante EXANI III ≥1000 Puntos de CENEVAL.',null,FALSE,TRUE,1),
--4
('Solicitud de Ingreso','Solicitud de Ingreso y Exposición de Motivos',null,TRUE,TRUE,1),
--5
--('Entrevista','Entrevista con Comité de Admisión.',null,FALSE,FALSE,6),
--6
('Comprobante Inglés','Comprobante Inglés ≥ 400 Puntos TOEFL o Nivel IV del Centro de Lenguas Extranjeras del ITCJ o Equivalente.',null,FALSE,TRUE,2),
--7
('Certificado de Licenciatura','Certificado de Estudios de Licenciatura.',null,FALSE,TRUE,2),
--8
('Título','Título de Licenciatura o Acta de Examen de Grado.',null,FALSE,TRUE,2),
--9
('Examen de Conocimientos','Acreditar Examen de Conocimientos: Matemáticas y Probabilidad y Estadística. Para las Maestrías de Ingeniería Industrial/Administrativa',null,TRUE,TRUE,3),
--10
('Examen de Conocimientos','Acreditar Examen de Conocimientos: Administración y Probabilidad - Estadística. Para la Maestría en Negocios Internacionales',null,TRUE,TRUE,4),
--11
('Certificado de Maestría','Certificado de Estudios de Maestría.',null,FALSE, TRUE,5),
--12
('Título','Título de Maestría o Acta de Examen de Grado.',null,FALSE,TRUE,5),
--13
('Comprobante de Inglés','Comprobante de Inglés ≥450 Puntos TOEFL o Equivalente.',null,FALSE,TRUE,5),
--14
('Examen de Conocimientos','Acreditar Examen de Conocimientos: Matemáticas / Probabilidad y Estadística. Para el Doctorado',null,FALSE,TRUE,5),
--15
('Protocolo/Propuesta de Investigación','Protocolo/Propuesta de Investigación Avalado por Claustro Doctoral.',null,FALSE,TRUE,5),
--16
--('Defensa de Protocolo/Propuesta','Defensa de Protocolo/Propuesta de Investigación con Comité de Admisión.',null,TRUE,FALSE,7),
--17
('Probabilidad - Estadística','Temario sobre Probabilidad - Estadística',null,TRUE,FALSE,8),
--18
('Administración','Temario para Administración',null,TRUE,FALSE,8),
--19
('Matemáticas','Temario para Matemáticas',null,TRUE,FALSE,8);
-- === Phase: Permanence ===
INSERT INTO archive (name, description, file_path, is_downloadable, is_uploadable, step_id) VALUES
--1
('Mapa Curricular', 'Mapa Curricular del Programa que Cursa.',null,TRUE,FALSE,9),
--2
('Programación de Materias','Programación de Materias/Tira de Materias',null,TRUE, TRUE,9),
--3
('Boleta de Inscripción','Boleta de Inscripción/Reinscripción Firmada/Sellada',null,FALSE,TRUE,9),
--4
('Boleta de Calificación Firmada/Sellada','Boleta de Calificación Firmada/Sellada',null,FALSE,TRUE,9),
--5
('Reporte de Retroalimentación','Reporte de Retroalimentación Comité Tutorial (Acta de Evaluación)',null,FALSE,FALSE,9),
--6
('Solicitud de Baja Temporal','Solicitud de Baja Temporal',null,TRUE,TRUE,9),
--7
('Carta del Director','Carta del Director de Tesis Similitud <30%',null,TRUE,TRUE,9),
--8
('Carta Solicitud','Carta Solicitud Avalada por Director de Tesis',null,TRUE,TRUE,10),
--9
('Carta de Aceptación','Carta de Aceptación',null,TRUE,TRUE,10),
--10
('Carta de Terminación','Carta de Terminación',null,TRUE,TRUE,10),
--11
('Informe Final','Informe Final Avalado por Receptor Responsable',null,FALSE,TRUE,10),
--12
('Protocolo de Investigación','Protocolo de Investigación Avalado por Director de Tesis',null,FALSE,TRUE,11),
--13
('Plan de Actividades','Propuesta del Plan de Actividades',null,FALSE,TRUE,11),
--14
('Carta Alta de Actividad','Carta Solicitando Alta de Actividad de Retribución Social con el Aval del Director de Tesis',null,TRUE,TRUE,11),
--15
('Carta de Terminación','Carta de Terminación de Retribución Social Avalada por el Director de Tesis',null,TRUE,TRUE,11),
--16
('Formato de Desempeño','Formato de Desempeño',null,TRUE,TRUE,12);

-- === Phase: Conclusion ===
INSERT INTO archive (name, description, file_path, is_downloadable, is_uploadable , step_id) VALUES
--1
('Título del Grado Anterior', 'Título del Grado Anterior o Acta de Examen de Grado.',null,FALSE,TRUE,13),
--2
('Solicitud del Examen de Grado','Solicitud al (a la) Jefe(a) de la DEPI, Fecha, Hora y Lugar para Realizar el Examen de Grado.',null,TRUE,TRUE,13),
--3
('Constancia de Aprobación','Constancia de Aprobación de la Totalidad de la Estructura Académica del Programa, Emitida por el Departamento de Servicios Escolares (Promedio=>80)',null,FALSE,TRUE,13),
--4
('Constancia de Segundo Idioma','Constancia del Manejo de un Segundo Idioma',null,FALSE,TRUE, 13),
--5
('Carta de Autorización','Carta de Autorización de Impresión de la Tesis Emitida por los Miembros del Comité Tutorial.',null,TRUE,TRUE,13),
--6
('Autorización de Impresión','Autorización de Impresión de la Tesis Emitida por la DEPI.',null,TRUE,TRUE,13),
--7
('Documento de Tesis Final','Documento de Tesis Final (PDF).',null,FALSE,TRUE,13),
--8
('Carta de Cesión de Derechos','Carta de Cesión de Derechos con Firma Autógrafa del Estudiante.',null,TRUE,TRUE,13),
--9
('Carta de Originalidad','Carta de Originalidad, Emitida por la Coordinación del Posgrado con Similitud >30%.',null,TRUE,TRUE,13),
--10
('Constancia de No Inconveniencia','Constancia de No Inconveniencia Emitida por Departamento de Servicios Escolares.',null,FALSE,TRUE,13),
--11
('Cobertura de los Derechos de Examen','Documento que Avale la Cobertura de los Derechos de Examen y de Expedición de los Documentos.',null,FALSE,TRUE,13),
--12
('No Adeudos','Documento de No Adeudo Económicos, ni de Material, ni de Equipo con las Oficinas, Laboratorios, Talleres y Biblioteca del Plantel.',null,FALSE,TRUE,13),
--13
('Oficio Autorización (Dispensa)','Oficio Autorización (Dispensa) en Caso de Haber Solicitado Presentar el Examen de Forma Extemporánea.',null,FALSE,TRUE,13),
--14
('Comprobante Actividades de Retribución','Comprobante de Dos Actividades de Retribución Social Durante su Estancia en el Programa, Avalada por su Director(a) de Tesis.',null,TRUE,TRUE,13),
--15
('Carta de Usuario','Carta de Usuario, que Indique la Incidencia y el Grado de Satisfacción del Proyecto de Tesis.',null,FALSE,TRUE,14),
--16
('Producto Académico Original','Producto Académico Original (ver Sección 4.5) Derivado de su Trabajo de Tesis Avalado por el Consejo de Posgrado.',null,FALSE,TRUE,14),
--17
('Estancia Académica','Estancia Académica si la Investigación lo Requiera con el Aval del Comité Tutorial.',null,FALSE,TRUE,15),
--18
('Artículo Publicado','Artículo Publicado o Aceptado en Revista Indizada JCR o de Índice CONAHCyT (ver Sección 4.5) o Registro de Patente.',null,FALSE,TRUE,15);