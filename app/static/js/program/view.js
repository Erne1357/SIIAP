// ────────────────────────────────────────────────────────────── 
// app/static/js/program/view.js
// ────────────────────────────────────────────────────────────── 

document.addEventListener('DOMContentLoaded', function() {
  // Obtener el contenedor principal scrolleable
  // Inicializar AOS (Animate On Scroll)
   AOS.init({
    duration: 800,
    once: true,
    easing: 'ease-in-out',
    offset: 50
  });

  // Smooth scroll para los enlaces de navegación dentro del contenido principal
  document.querySelectorAll('.program-view-container a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      
      const targetElement = document.querySelector(targetId);
      if (!targetElement) return;
      
      // Obtener el contenedor principal scrolleable (main-content)
      const mainContent = document.getElementById('main-content');
      
      // Calcular la posición del elemento dentro del contenedor scrolleable
      const targetPosition = targetElement.offsetTop - mainContent.offsetTop;

      // Hacer scroll dentro del contenedor principal
      mainContent.scrollTo({
        top: targetPosition - 20, // Añadir un pequeño margen
        behavior: 'smooth'
      });
    });
  });

  // Activar tooltips de Bootstrap
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function(tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Validación de formulario de contacto
  const contactForm = document.querySelector('.program-view-container form');
  if (contactForm) {
    contactForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      // Aquí puedes agregar la lógica de validación del formulario
      let isValid = true;
      const name = document.getElementById('name');
      const email = document.getElementById('email');
      const message = document.getElementById('message');
      
      if (!name.value.trim()) {
        isValid = false;
        name.classList.add('is-invalid');
      } else {
        name.classList.remove('is-invalid');
      }
      
      if (!email.value.trim() || !isValidEmail(email.value)) {
        isValid = false;
        email.classList.add('is-invalid');
      } else {
        email.classList.remove('is-invalid');
      }
      
      if (!message.value.trim()) {
        isValid = false;
        message.classList.add('is-invalid');
      } else {
        message.classList.remove('is-invalid');
      }
      
      if (isValid) {
        // Aquí puedes enviar el formulario o mostrar un mensaje de éxito
        alert('Mensaje enviado correctamente. Te contactaremos pronto.');
        contactForm.reset();
      }
    });
  }

  // Función para validar email
  function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  }

  // Abrir el primer elemento del acordeón en cada fase
  document.querySelectorAll('.accordion').forEach(accordion => {
    // Descomenta estas líneas si quieres que el primer elemento esté abierto por defecto
    // const firstButton = accordion.querySelector('.accordion-button');
    // const firstCollapse = accordion.querySelector('.accordion-collapse');
    // if (firstButton && firstCollapse) {
    //   firstButton.classList.remove('collapsed');
    //   firstButton.setAttribute('aria-expanded', 'true');
    //   firstCollapse.classList.add('show');
    // }
  });

  // Ajustar la altura de las tarjetas para que sean iguales en cada fila
  function equalizeCardHeights() {
    const cardRows = document.querySelectorAll('.row');
    
    cardRows.forEach(row => {
      const cards = row.querySelectorAll('.card');
      if (cards.length > 1) {
        // Resetear alturas
        cards.forEach(card => {
          card.style.height = 'auto';
        });
        
        // Encontrar la altura máxima
        let maxHeight = 0;
        cards.forEach(card => {
          const height = card.offsetHeight;
          if (height > maxHeight) {
            maxHeight = height;
          }
        });
        
        // Aplicar altura máxima a todas las tarjetas
        cards.forEach(card => {
          card.style.height = maxHeight + 'px';
        });
      }
    });
  }

    // Función para manejar el cambio de tabs en el proceso de admisión
  const admissionTabs = document.querySelectorAll('#admissionPhasesTab button');
  if (admissionTabs.length > 0) {
    admissionTabs.forEach(tab => {
      tab.addEventListener('shown.bs.tab', function (e) {
        // Refrescar AOS cuando se cambia de tab
        setTimeout(() => {
          AOS.refresh();
        }, 150);
      });
    });
  }
  
  // Hacer que los botones flotantes aparezcan con animación
   // Hacer que los botones flotantes aparezcan con animación
  const floatingBackButton = document.querySelector('.floating-back-button');
  const floatingInscriptionButton = document.querySelector('.floating-inscription-button');
  const mainContent = document.getElementById('main-content');
  
  if (floatingBackButton && floatingInscriptionButton) {
    // Añadir clase para animación después de un breve retraso
    setTimeout(() => {
      floatingBackButton.classList.add('visible');
      floatingInscriptionButton.classList.add('visible');
    }, 500);
    
    // Ocultar botón de inscripción al hacer scroll hacia abajo y mostrarlo al subir
    let lastScrollTop = 0;
    mainContent.addEventListener('scroll', function() {
      const st = mainContent.scrollTop;
      if (st > lastScrollTop && st > 300) {
        // Scroll hacia abajo
        floatingInscriptionButton.style.opacity = '0';
        floatingInscriptionButton.style.transform = 'translateY(20px)';
      } else {
        // Scroll hacia arriba
        floatingInscriptionButton.style.opacity = '1';
        floatingInscriptionButton.style.transform = 'translateY(0)';
      }
      lastScrollTop = st;
    });
  }
  // Ejecutar después de que las imágenes se hayan cargado
  window.addEventListener('load', equalizeCardHeights);
  // También ejecutar cuando se redimensione la ventana
  window.addEventListener('resize', equalizeCardHeights);

   document.addEventListener('swup:contentReplaced', () => {
    AOS.refreshHard();
  });
});