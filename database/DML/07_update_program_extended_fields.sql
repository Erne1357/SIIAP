-- 07_update_program_extended_fields.sql
-- Actualizar programas con información extendida que estaba hardcodeada en los templates

-- ============================================
-- 1. Maestría en Ingeniería Industrial (MII)
-- ============================================
UPDATE program SET
    program_level = 'Maestría',
    academic_area = 'Ingeniería',
    image_filename = 'Maestría en Ingeniería Industrial.webp',
    is_active = TRUE,
    duration_semesters = 4,
    duration_years = 2.0,
    modality = 'Presencial con recursos digitales',
    schedule_info = NULL,
    introduction_text = 'Formar profesionistas con un alto conocimiento y sentido innovador en la aplicación de la Ingeniería Industrial que de acuerdo a la problemática regional, nacional y global y a las tendencias de investigación de frontera, desarrollen sus capacidades para afrontar los retos de las empresas modernas plantean.',
    recognition_text = 'Programa reconocido por su excelencia académica',
    scholarship_info = 'Posibilidad de becas para estudiantes',
    admission_requirements = NULL,
    objectives = '["Formar especialistas en ciencias de la computación con sólidos conocimientos teóricos y prácticos", "Desarrollar habilidades para el análisis y solución de problemas computacionales complejos", "Fomentar la investigación aplicada en el campo de la computación", "Preparar profesionales con capacidad de liderazgo en proyectos tecnológicos"]'::json,
    graduate_profile_intro = 'El egresado de la Maestría en Ciencias de la Computación será capaz de:',
    graduate_competencies = '["Diseñar e implementar soluciones computacionales avanzadas para problemas complejos", "Aplicar metodologías de investigación en el campo de las ciencias de la computación", "Liderar equipos de desarrollo tecnológico en entornos profesionales", "Continuar estudios de doctorado en áreas afines a las ciencias computacionales"]'::json,
    research_lines = NULL,
    curriculum_structure = '{
        "type": "semestral",
        "semesters": [
            {
                "number": 1,
                "name": "Primer Semestre",
                "subjects": [
                    "Fundamentos de Computación Avanzada",
                    "Metodología de la Investigación",
                    "Matemáticas para Computación"
                ]
            },
            {
                "number": 2,
                "name": "Segundo Semestre",
                "subjects": [
                    "Algoritmos y Estructuras de Datos",
                    "Análisis y Diseño de Sistemas",
                    "Optativa I"
                ]
            },
            {
                "number": 3,
                "name": "Tercer Semestre",
                "subjects": [
                    "Seminario de Tesis I",
                    "Optativa II",
                    "Optativa III"
                ]
            },
            {
                "number": 4,
                "name": "Cuarto Semestre",
                "subjects": [
                    "Seminario de Tesis II",
                    "Trabajo de Tesis",
                    "Defensa de Tesis"
                ]
            }
        ]
    }'::json,
    show_curriculum = TRUE,
    contact_email = 'maestria.cc@universidad.edu',
    contact_email_secondary = 'admisiones@universidad.edu',
    contact_phone = '+52 (123) 456-7890',
    contact_phone_secondary = '+52 (123) 456-7891',
    contact_address = 'Av. Universidad 3000, Ciudad Universitaria, Coyoacán, 04510, Ciudad de México',
    contact_office = NULL,
    contact_hours = NULL,
    show_hero_cards = TRUE,
    show_objectives = TRUE,
    show_graduate_profile = TRUE,
    show_research_lines = TRUE,
    show_contact_section = TRUE,
    show_contact_form = TRUE,
    meta_title = NULL,
    meta_description = NULL,
    meta_keywords = NULL
WHERE slug = 'MII';

-- ============================================
-- 2. Maestría en Administración de Negocios Internacionales (MANI)
-- ============================================
UPDATE program SET
    program_level = 'Maestría',
    academic_area = 'Administración',
    image_filename = 'Maestría en Administración de Negocios Internacionales.webp',
    is_active = TRUE,
    duration_semesters = 4,
    duration_years = 2.0,
    modality = 'Presencial con recursos digitales',
    schedule_info = NULL,
    introduction_text = 'En México una parte significativa de su crecimiento económico depende de los negocios internacionales, específicamente del comercio exterior acompañado de la inversión extranjera. La Maestría en Administración de Negocios Internacionales tiene como uno de sus objetivos formar el capital humano que requiere esta dinámica de los negocios internacionales, la cual ya es una práctica común en la economía mexicana.',
    recognition_text = 'Programa reconocido por su excelencia académica',
    scholarship_info = 'Posibilidad de becas para estudiantes',
    admission_requirements = NULL,
    objectives = '["Formar especialistas en inteligencia artificial con conocimientos avanzados", "Desarrollar habilidades para implementar soluciones basadas en IA", "Fomentar la investigación en áreas emergentes de la inteligencia artificial", "Preparar profesionales capaces de liderar la transformación digital mediante IA"]'::json,
    graduate_profile_intro = 'El egresado de la Maestría en Inteligencia Artificial será capaz de:',
    graduate_competencies = '["Diseñar e implementar sistemas basados en inteligencia artificial para resolver problemas complejos", "Aplicar técnicas avanzadas de aprendizaje automático y procesamiento de datos", "Liderar proyectos de innovación tecnológica basados en IA", "Continuar estudios de doctorado en áreas relacionadas con la inteligencia artificial"]'::json,
    research_lines = NULL,
    curriculum_structure = '{
        "type": "semestral",
        "semesters": [
            {
                "number": 1,
                "name": "Primer Semestre",
                "subjects": [
                    "Fundamentos de Inteligencia Artificial",
                    "Matemáticas para IA",
                    "Programación para IA"
                ]
            },
            {
                "number": 2,
                "name": "Segundo Semestre",
                "subjects": [
                    "Aprendizaje Automático",
                    "Procesamiento de Lenguaje Natural",
                    "Optativa I"
                ]
            },
            {
                "number": 3,
                "name": "Tercer Semestre",
                "subjects": [
                    "Visión por Computadora",
                    "Sistemas Inteligentes",
                    "Optativa II"
                ]
            },
            {
                "number": 4,
                "name": "Cuarto Semestre",
                "subjects": [
                    "Seminario de Tesis",
                    "Trabajo de Tesis",
                    "Defensa de Tesis"
                ]
            }
        ]
    }'::json,
    show_curriculum = TRUE,
    contact_email = 'maestria.ia@universidad.edu',
    contact_email_secondary = 'admisiones@universidad.edu',
    contact_phone = '+52 (123) 456-7890',
    contact_phone_secondary = '+52 (123) 456-7891',
    contact_address = 'Av. Universidad 3000, Ciudad Universitaria, Coyoacán, 04510, Ciudad de México',
    contact_office = NULL,
    contact_hours = NULL,
    show_hero_cards = TRUE,
    show_objectives = TRUE,
    show_graduate_profile = TRUE,
    show_research_lines = TRUE,
    show_contact_section = TRUE,
    show_contact_form = TRUE,
    meta_title = NULL,
    meta_description = NULL,
    meta_keywords = NULL
WHERE slug = 'MANI';

-- ============================================
-- 3. Maestría en Ingeniería Administrativa (MIA)
-- ============================================
UPDATE program SET
    program_level = 'Maestría',
    academic_area = 'Ingeniería',
    image_filename = 'Maestría en Ingeniería Administrativa.webp',
    is_active = TRUE,
    duration_semesters = 4,
    duration_years = 2.0,
    modality = 'Presencial con recursos digitales',
    schedule_info = NULL,
    introduction_text = 'La Ingeniería Administrativa da un amplio conocimiento técnico con un énfasis especial sobre productividad, costos, calidad, administración y el factor humano en los sistemas de producción y operacionales, además conjunta conocimientos y habilidades especializadas de ciencias matemáticas, físicas y sociales con los principios y métodos de diseño y análisis de ingeniería para especificar, predecir y evaluar sistemas productivos de bienes o servicios.',
    recognition_text = 'Programa reconocido por su excelencia académica',
    scholarship_info = 'Posibilidad de becas para estudiantes',
    admission_requirements = NULL,
    objectives = '["Formar profesionales especializados en el área", "Desarrollar habilidades para la resolución de problemas complejos", "Fomentar la investigación y el desarrollo tecnológico", "Preparar líderes con compromiso ético en su campo"]'::json,
    graduate_profile_intro = 'El egresado de este programa será capaz de:',
    graduate_competencies = '["Aplicar conocimientos especializados para la resolución de problemas en su área", "Desarrollar proyectos de investigación y desarrollo tecnológico", "Integrarse a equipos multidisciplinarios en entornos profesionales", "Continuar su formación académica en niveles superiores"]'::json,
    research_lines = NULL,
    curriculum_structure = '{
        "type": "semestral",
        "semesters": [
            {
                "number": 1,
                "name": "Primer Semestre",
                "subjects": [
                    "Seminario de Investigación I",
                    "Metodología Avanzada"
                ]
            },
            {
                "number": 2,
                "name": "Segundo Semestre",
                "subjects": [
                    "Seminario de Investigación II",
                    "Tópicos Avanzados I"
                ]
            },
            {
                "number": 3,
                "name": "Tercer Semestre",
                "subjects": [
                    "Seminario de Investigación III",
                    "Tópicos Avanzados II"
                ]
            },
            {
                "number": 4,
                "name": "Cuarto Semestre",
                "subjects": [
                    "Seminario de Investigación IV",
                    "Avance de Tesis Doctoral"
                ]
            }
        ]
    }'::json,
    show_curriculum = TRUE,
    contact_email = 'posgrado@universidad.edu',
    contact_email_secondary = 'admisiones@universidad.edu',
    contact_phone = '+52 (123) 456-7890',
    contact_phone_secondary = '+52 (123) 456-7891',
    contact_address = 'Av. Universidad 3000, Ciudad Universitaria, Coyoacán, 04510, Ciudad de México',
    contact_office = NULL,
    contact_hours = NULL,
    show_hero_cards = TRUE,
    show_objectives = TRUE,
    show_graduate_profile = TRUE,
    show_research_lines = TRUE,
    show_contact_section = TRUE,
    show_contact_form = TRUE,
    meta_title = NULL,
    meta_description = NULL,
    meta_keywords = NULL
WHERE slug = 'MIA';

-- ============================================
-- 4. Doctorado en Ciencias de la Ingeniería (DCI)
-- ============================================
UPDATE program SET
    program_level = 'Doctorado',
    academic_area = 'Ingeniería',
    image_filename = 'Doctorado en Ciencias de la Ingeniería.webp',
    is_active = TRUE,
    duration_semesters = 6,
    duration_years = 3.0,
    modality = 'Presencial con recursos digitales',
    schedule_info = NULL,
    introduction_text = 'El DCI tiene como objetivos el formar a investigadores de alto nivel con las competencias científicas y tecnológicas para generar nuevos conocimientos, y desarrollar proyectos de innovación, adaptación, mejoramiento y optimización de procesos de ingeniería. Las líneas de generación y aplicación del conocimiento (LGAC) a desarrollar son: a) Optimización de Productos y Procesos (OPP) b) Modelación y Simulación de Procesos (MSP)',
    recognition_text = 'Programa reconocido por su excelencia académica',
    scholarship_info = 'Posibilidad de becas para estudiantes',
    admission_requirements = NULL,
    objectives = '["Formar investigadores de alto nivel en ciencias de la computación", "Desarrollar capacidades para generar conocimiento original en el campo", "Fomentar la colaboración interdisciplinaria en proyectos de investigación", "Contribuir al avance científico y tecnológico mediante investigación de frontera"]'::json,
    graduate_profile_intro = 'El egresado del Doctorado en Ciencias de la Computación será capaz de:',
    graduate_competencies = '["Generar conocimiento original en el campo de las ciencias de la computación", "Dirigir proyectos de investigación de alto nivel en entornos académicos y profesionales", "Formar recursos humanos especializados en el área", "Contribuir al avance científico y tecnológico mediante publicaciones de impacto internacional"]'::json,
    research_lines = NULL,
    curriculum_structure = NULL,
    show_curriculum = FALSE,
    contact_email = 'doctorado.cc@universidad.edu',
    contact_email_secondary = 'admisiones@universidad.edu',
    contact_phone = '+52 (123) 456-7890',
    contact_phone_secondary = '+52 (123) 456-7891',
    contact_address = 'Av. Universidad 3000, Ciudad Universitaria, Coyoacán, 04510, Ciudad de México',
    contact_office = NULL,
    contact_hours = NULL,
    show_hero_cards = TRUE,
    show_objectives = TRUE,
    show_graduate_profile = TRUE,
    show_research_lines = TRUE,
    show_contact_section = TRUE,
    show_contact_form = TRUE,
    meta_title = NULL,
    meta_description = NULL,
    meta_keywords = NULL
WHERE slug = 'DCI';
