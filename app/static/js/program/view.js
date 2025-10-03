// ────────────────────────────────────────────────────────────── 
// app/static/js/program/view.js
// ────────────────────────────────────────────────────────────── 

document.addEventListener('DOMContentLoaded', function() {
  // Debug: Verificar que los elementos AOS existen
  console.log('Elementos con data-aos encontrados:', document.querySelectorAll('[data-aos]').length);
  
  // Obtener el contenedor principal scrolleable
  // Implementar AOS personalizado para contenedor con scroll
  function initCustomAOS() {
    const mainContent = document.getElementById('main-content');
    const elementsToAnimate = document.querySelectorAll('[data-aos]');
    
    if (!mainContent || elementsToAnimate.length === 0) return;
    
    // Función para verificar si un elemento está visible en el contenedor
    function isElementInViewport(el, container) {
      const containerRect = container.getBoundingClientRect();
      const elementRect = el.getBoundingClientRect();
      
      const containerTop = containerRect.top;
      const containerBottom = containerRect.bottom;
      const elementTop = elementRect.top;
      const elementBottom = elementRect.bottom;
      
      // Margen de activación (más generoso)
      const offset = 150;
      
      // Elemento está visible si cualquier parte está dentro del viewport del contenedor
      const isVisible = (elementTop <= containerBottom + offset && elementBottom >= containerTop - offset);
      
      return isVisible;
    }
    
    // Función para activar animaciones
    function activateAnimations() {
      let animatedCount = 0;
      elementsToAnimate.forEach((element, index) => {
        if (isElementInViewport(element, mainContent)) {
          if (!element.classList.contains('aos-animate')) {
            // Aplicar delay si existe
            const delay = element.getAttribute('data-aos-delay') || 0;
            
            setTimeout(() => {
              element.classList.add('aos-animate');
              element.style.transform = 'translateY(0) translateX(0)';
              element.style.opacity = '1';
              animatedCount++;
            }, parseInt(delay));
          }
        }
      });
      
      if (animatedCount > 0) {
        console.log(`Animando ${animatedCount} elementos`);
      }
    }
    
    // Configurar estilos iniciales
    elementsToAnimate.forEach(element => {
      const animationType = element.getAttribute('data-aos') || 'fade-up';
      element.style.transition = 'all 800ms ease-in-out';
      
      if (animationType.includes('fade-up')) {
        element.style.transform = 'translateY(30px)';
        element.style.opacity = '0';
      } else if (animationType.includes('fade-in')) {
        element.style.opacity = '0';
      } else if (animationType.includes('fade-left')) {
        element.style.transform = 'translateX(30px)';
        element.style.opacity = '0';
      } else if (animationType.includes('fade-right')) {
        element.style.transform = 'translateX(-30px)';
        element.style.opacity = '0';
      }
    });
    
    // Activar inmediatamente para elementos ya visibles
    activateAnimations();
    
    // Escuchar scroll en el contenedor principal
    mainContent.addEventListener('scroll', activateAnimations);
    
    // También activar en resize
    window.addEventListener('resize', activateAnimations);
    
    return activateAnimations;
  }
  
  // Inicializar AOS personalizado
  const activateAnimations = initCustomAOS();

  // Smooth scroll para los enlaces de navegación dentro del contenido principal
  document.querySelectorAll('.program-view-container a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      
      const targetElement = document.querySelector(targetId);
      if (!targetElement) return;
      
      // Calcular la posición del elemento en la página completa
      const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset;

      // Hacer scroll en toda la página
      window.scrollTo({
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
        // Activar animaciones personalizadas cuando se cambia de tab
        setTimeout(() => {
          if (typeof activateAnimations === 'function') {
            activateAnimations();
          }
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
      
      // Activar animaciones personalizadas en cada scroll
      if (typeof activateAnimations === 'function') {
        activateAnimations();
      }
      
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

  // Manejar eventos de Swup para reinicializar AOS personalizado
  document.addEventListener('swup:contentReplaced', () => {
    // Reinicializar AOS personalizado
    setTimeout(() => {
      initCustomAOS();
    }, 100);
  });

  // Función para forzar la detección después de la carga
  setTimeout(() => {
    if (typeof activateAnimations === 'function') {
      activateAnimations();
    }
    // Segundo intento para elementos que se cargan dinámicamente
    setTimeout(() => {
      if (typeof activateAnimations === 'function') {
        activateAnimations();
      }
    }, 500);
  }, 200);
});