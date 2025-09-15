-- insert_archive.sql
-- === Phase: Admission ===
INSERT INTO archive (name, description, file_path, is_downloadable,is_uploadable, step_id) VALUES
--1
('Currículum Vitae','Currículum Vitae con documentos probatorios.',null,FALSE,TRUE,1),
--2
('Cartas de Recomendación','Cartas de Recomendación (2) Dirigidas al Comité de Admisión firmadas por especialistas externos al plantel.',null,TRUE,TRUE,1),
--3
('Comprobante EXANI III.','Comprobante EXANI III ≥1000 puntos de CENEVAL.',null,FALSE,TRUE,1),
--4
('Solicitud de ingreso','Solicitud de ingreso y exposición de motivos',null,TRUE,TRUE,1),
--5
('Entrevista','Entrevista con Comité de Admisión.',null,FALSE,FALSE,6),
--6
('Comprobante Inglés','Comprobante Inglés ≥ 400 puntos TOEFL o  nivel IV del Centro de Lenguas Extranjeras del ITCJ o equivalente.',null,FALSE,TRUE,2),
--7
('Certificado de Licenciatura.','Certificado de Estudios de Licenciatura.',null,FALSE,TRUE,2),
--8
('Titulo','Titulo de Licenciatura o Acta de Examen de Grado.',null,FALSE,TRUE,2),
--9
('Examen de conocimientos','Acreditar examen de conocimientos: Matemáticas y Probabilidad y Estadística. Para las maestrías de Ingeniería Industrial/Administrativa',null,TRUE,TRUE,3),
--10
('Examen de conocimientos','Acreditar examen de conocimientos: Administración y Probabilidad - Estadística. Para la maestría de en negocios Internacionales',null,TRUE,TRUE,4),
--11
('Certificado de Maestría.','Certificado de Estudios de Maestría.',null,FALSE, TRUE,5),
--12
('Titulo','Titulo de Maestría o Acta de Examen de Grado.',null,FALSE,TRUE,5),
--13
('Comprobante de Inglés','Comprobante de Inglés≥450 puntos TOEFL O equivalente.',null,FALSE,TRUE,5),
--14
('Examen de conocimientos','Acreditar examen de conocimientos: Matemáticas / Probabilidad y Estadística. Para el doctorado',null,FALSE,TRUE,5),
--15
('Protocolo/propuesta de investigación','Protocolo/propuesta de investigación avalado por claustro doctoral.',null,FALSE,TRUE,5),
--16
('Defensa de protocolo/propuesta','Defensa de protocolo/propuesta de investigación con Comité de admisión.',null,TRUE,FALSE,7),
--17
('Probabilidad - Estadística','Temario sobre Probabilidad - Estadística',null,TRUE,FALSE,8),
--18
('Administración','Temario para Administración',null,TRUE,FALSE,8),
--19
('Matemáticas','Temario para Matemáticas',null,TRUE,FALSE,8);
-- === Phase: Permanence ===
INSERT INTO archive (name, description, file_path, is_downloadable, is_uploadable, step_id) VALUES
--1
('Mapa Curricular', 'Mapa curricular del programa que cursa.',null,TRUE,FALSE,9),
--2
('Programación de Materias','Programación de Materias/Tira de materias',null,TRUE, TRUE,9),
--3
('Boleta de Inscripción','Boleta de Inscripción/Reinscripción Firmada/Sellada',null,FALSE,TRUE,9),
--4
('Boleta de Calificación Firmada/Sellada','Boleta de Calificación Firmada/Sellada',null,FALSE,TRUE,9),
--5
('Reporte de Retroalimentación','Reporte de Retroalimentación Comité Tutorial (acta de evaluación)',null,FALSE,FALSE,9),
--6
('Solicitud de Baja Temporal','Solicitud de Baja Temporal',null,TRUE,TRUE,9),
--7
('Carta del Director','Carta del Director de Tesis Similitud <30%',null,TRUE,TRUE,9),
--8
('Carta Solicitud','Carta Solicitud avalada por Director de Tesis',null,TRUE,TRUE,10),
--9
('Carta de Aceptación','Carta de Aceptación',null,TRUE,TRUE,10),
--10
('Carta de Terminación','Carta de Terminación',null,TRUE,TRUE,10),
--11
('Informe Final','Informe Final Avalado por Receptor Responsable',null,FALSE,TRUE,10),
--12
('Protocolo de Investigación','Protocolo de Investigación avalado por Director de Tesis',null,FALSE,TRUE,11),
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
('Titulo del grado anterior', 'Titulo del grado anterior o Acta de Examen de Grado.',null,FALSE,TRUE,13),
--2
('Solicitud del examen de grado','Solicitud al (a la) jefe(a) de la DEPI, fecha, hora y lugar para realizar el Examen de grado.',null,TRUE,TRUE,13),
--3
('Constancia de aprobación','Constancia de aprobación de la totalidad de la estructura académica del programa, emitida por el Departamento de Servicios Escolares (promedio=>80)',null,FALSE,TRUE,13),
--4
('Constancia de segundo idioma','Constancia del manejo de un segundo idioma',null,FALSE,TRUE, 13),
--5
('Carta de autorización','Carta de autorización de impresión de la tesis emitida por los miembros del Comité Tutorial.',null,TRUE,TRUE,13),
--6
('Autorización de impresión','Autorización de impresión de la tesis emitida por la DEPI.',null,TRUE,TRUE,13),
--7
('Documento de Tesis Final','Documento de Tesis Final (PDF).',null,FALSE,TRUE,13),
--8
('Carta de cesión de derechos','Carta de cesión de derechos con firma autógrafa del estudiante.',null,TRUE,TRUE,13),
--9
('Carta de originalidad','Carta de originalidad, emitida por la Coordinación del Posgrado con similitud >30%.',null,TRUE,TRUE,13),
--10
('Constancia de No Inconveniencia','Constancia de No Inconveniencia emitida poR Departamento de Servicios Escolares.',null,FALSE,TRUE,13),
--11
('Cobertura de los derechos de examen','Documento que avale la cobertura de los derechos de examen y de expedición de los documentos.',null,FALSE,TRUE,13),
--12
('No adeudos','Documento de no adeudo económicos, ni de material, ni de equipo con las oficinas, laboratorios, talleres y biblioteca del plantel.',null,FALSE,TRUE,13),
--13
('Oficio Autorización (dispensa)','Oficio Autorización (dispensa) en caso de haber solicitado presentar el examen de forma extemporánea.',null,FALSE,TRUE,13),
--14
('Comprobante actividades de retribución','Comprobante de dos actividades de retribución social durante su estancia en el programa, avalada por su director(a) de tesis.',null,TRUE,TRUE,13),
--15
('Carta de usuario','Carta de usuario, que indique la incidencia y el grado de satisfacción del proyecto de tesis.',null,FALSE,TRUE,14),
--16
('Producto académico original','Producto académico original (ver sección 4.5) derivado de su trabajo de tesis avalado por el Consejo de Posgrado.',null,FALSE,TRUE,14),
--17
('Estancia académica ','Estancia académica si la investigación lo requiera con el aval del Comité Tutorial.',null,FALSE,TRUE,15),
--18
('Articulo Publicado','Articulo Publicado o aceptado en revista indizada JCR o de índice CONAHCyT (ver sección 4.5) o registro de patente.',null,FALSE,TRUE,15);