// app/static/js/program/program_transfer.js
(function() {
  'use strict';
  
  const getCsrf = () => {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
  };
  
  function flash(message, level = 'success') {
    window.dispatchEvent(new CustomEvent('flash', { 
      detail: { level: level, message: message } 
    }));
  }
  
  // State global
  let currentAnalysis = null;
  let currentFromProgram = null;
  let currentToProgram = null;
  
  // ==================== INICIALIZAR ====================
  document.addEventListener('DOMContentLoaded', () => {
    initTransferButton();
    initModalEvents();
  });
  
  // ==================== BOTÓN DE CAMBIO ====================
  function initTransferButton() {
    const transferBtn = document.getElementById('btnRequestProgramChange');
    if (!transferBtn) return;
    
    transferBtn.addEventListener('click', async () => {
      const programId = transferBtn.dataset.programId;
      const programSlug = transferBtn.dataset.programSlug;
      
      if (!programId) {
        flash('Error: No se pudo identificar el programa actual', 'danger');
        return;
      }
      
      currentFromProgram = { id: parseInt(programId), slug: programSlug };
      
      // Cargar programas disponibles
      await loadAvailablePrograms();
      
      // Mostrar modal de selección
      const modal = new bootstrap.Modal(document.getElementById('selectProgramModal'));
      modal.show();
    });
  }
  
  // ==================== CARGAR PROGRAMAS ====================
  async function loadAvailablePrograms() {
    try {
      const res = await fetch('/api/v1/programs/', {
        credentials: 'same-origin'
      });
      
      if (!res.ok) throw new Error('Error cargando programas');
      
      const json = await res.json();
      const programs = json.data || [];
      console.log('Available programs:', programs);
      const container = document.getElementById('availableProgramsList');
      container.innerHTML = '';
      
      programs.forEach(prog => {
        console.log(prog);
        // No mostrar el programa actual
        if (prog.id === currentFromProgram.id) return;
        console.log('Adding program:', prog);
        const card = document.createElement('div');
        card.className = 'program-option card mb-2';
        card.innerHTML = `
          <div class="card-body">
            <div class="form-check">
              <input class="form-check-input" type="radio" name="targetProgram" 
                     id="prog-${prog.id}" value="${prog.id}" data-slug="${prog.slug}">
              <label class="form-check-label" for="prog-${prog.id}">
                <strong>${prog.name}</strong>
                <p class="small text-muted mb-0">${prog.description || ''}</p>
              </label>
            </div>
          </div>
        `;
        container.appendChild(card);
      });
      
    } catch (err) {
      console.error('Error loading programs:', err);
      flash('Error al cargar programas disponibles', 'danger');
    }
  }
  
  // ==================== EVENTOS DEL MODAL ====================
  function initModalEvents() {
    // Botón "Continuar" en modal de selección
    const btnContinueSelection = document.getElementById('btnContinueSelection');
    if (btnContinueSelection) {
      btnContinueSelection.addEventListener('click', async () => {
        const selected = document.querySelector('input[name="targetProgram"]:checked');
        if (!selected) {
          flash('Selecciona un programa', 'warning');
          return;
        }
        
        currentToProgram = {
          id: parseInt(selected.value),
          slug: selected.dataset.slug
        };
        
        // Cerrar modal de selección
        bootstrap.Modal.getInstance(document.getElementById('selectProgramModal')).hide();
        
        // Analizar transferencia
        await analyzeTransfer();
      });
    }
    
    // Botón "Confirmar Cambio" en modal de análisis
    const btnConfirmTransfer = document.getElementById('btnConfirmTransfer');
    if (btnConfirmTransfer) {
      btnConfirmTransfer.addEventListener('click', async () => {
        await executeTransfer();
      });
    }
    
    // Botón "Cancelar" en modal de análisis
    const btnCancelTransfer = document.getElementById('btnCancelTransfer');
    if (btnCancelTransfer) {
      btnCancelTransfer.addEventListener('click', () => {
        bootstrap.Modal.getInstance(document.getElementById('analysisModal')).hide();
      });
    }
  }
  
  // ==================== ANALIZAR TRANSFERENCIA ====================
  async function analyzeTransfer() {
    const analysisModal = new bootstrap.Modal(document.getElementById('analysisModal'));
    
    // Mostrar loading en el modal
    document.getElementById('analysisContent').innerHTML = `
      <div class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Analizando...</span>
        </div>
        <p class="mt-3">Analizando cambio de programa...</p>
      </div>
    `;
    
    analysisModal.show();
    
    try {
      const res = await fetch('/api/v1/program-changes/analyze', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': getCsrf()
        },
        body: JSON.stringify({
          from_program_id: currentFromProgram.id,
          to_program_id: currentToProgram.id
        })
      });
      
      const json = await res.json();
      
      if (!res.ok || !json.ok) {
        throw new Error(json.error || 'Error al analizar');
      }
      
      currentAnalysis = json.analysis;
      renderAnalysis(currentAnalysis);
      
    } catch (err) {
      console.error('Analysis error:', err);
      document.getElementById('analysisContent').innerHTML = `
        <div class="alert alert-danger">
          <i class="fas fa-exclamation-triangle me-2"></i>
          Error al analizar el cambio: ${err.message}
        </div>
      `;
      document.getElementById('btnConfirmTransfer').disabled = true;
    }
  }
  
  // ==================== RENDERIZAR ANÁLISIS ====================
  function renderAnalysis(analysis) {
    const container = document.getElementById('analysisContent');
    
    let html = '<div class="analysis-results">';
    
    // 1. Resumen general
    html += `
      <div class="alert alert-info mb-4">
        <h6 class="mb-2"><i class="fas fa-info-circle me-2"></i>Resumen del Cambio</h6>
        <ul class="mb-0 small">
          <li><strong>${analysis.reusable_docs.length}</strong> documento(s) se conservarán</li>
          <li><strong>${analysis.incompatible_docs.length}</strong> documento(s) se eliminarán</li>
          <li><strong>${analysis.missing_docs.length}</strong> documento(s) nuevo(s) requerido(s)</li>
        </ul>
      </div>
    `;
    
    // 2. Documentos que se conservan
    if (analysis.reusable_docs.length > 0) {
      html += `
        <div class="mb-4">
          <h6 class="text-success">
            <i class="fas fa-check-circle me-2"></i>
            Documentos que se Conservarán (${analysis.reusable_docs.length})
          </h6>
          <div class="table-responsive">
            <table class="table table-sm table-hover">
              <thead class="table-light">
                <tr>
                  <th>Documento</th>
                  <th>Estado</th>
                  <th>Paso Actual</th>
                  <th>Paso Nuevo</th>
                </tr>
              </thead>
              <tbody>
      `;
      
      analysis.reusable_docs.forEach(doc => {
        const statusBadge = doc.status === 'approved' 
          ? '<span class="badge bg-success">Aprobado</span>'
          : doc.status === 'rejected'
          ? '<span class="badge bg-danger">Rechazado</span>'
          : '<span class="badge bg-warning text-dark">En Revisión</span>';
        
        const matchType = doc.is_same_file 
          ? '<i class="fas fa-equals text-success" title="Archivo idéntico"></i>'
          : '<i class="fas fa-exchange-alt text-info" title="Archivo equivalente"></i>';
        
        html += `
          <tr>
            <td>
              ${doc.name} ${matchType}
              <div class="small text-muted">ID: ${doc.archive_id} → ${doc.target_archive_id}</div>
            </td>
            <td>${statusBadge}</td>
            <td class="small text-muted">${doc.from_step}</td>
            <td class="small text-muted">${doc.to_step}</td>
          </tr>
        `;
      });
      
      html += `
              </tbody>
            </table>
          </div>
          <p class="small text-muted mb-0">
            <i class="fas fa-info-circle me-1"></i>
            Estos documentos serán reutilizados en el nuevo programa. 
            Los aprobados volverán a estado "Pendiente" para nueva revisión.
          </p>
        </div>
      `;
    }
    
    // 3. Documentos que se eliminarán
    if (analysis.incompatible_docs.length > 0) {
      html += `
        <div class="mb-4">
          <h6 class="text-danger">
            <i class="fas fa-times-circle me-2"></i>
            Documentos que se Eliminarán (${analysis.incompatible_docs.length})
          </h6>
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Atención:</strong> Estos archivos NO son compatibles con el nuevo programa 
            y serán <strong>eliminados permanentemente</strong>.
          </div>
          <ul class="list-group">
      `;
      
      analysis.incompatible_docs.forEach(doc => {
        html += `
          <li class="list-group-item d-flex justify-content-between align-items-start">
            <div>
              <strong>${doc.name}</strong>
              <div class="small text-muted">Paso: ${doc.step_name}</div>
              <div class="small text-muted">ID: ${doc.archive_id}</div>
            </div>
            <i class="fas fa-trash text-danger"></i>
          </li>
        `;
      });
      
      html += `
          </ul>
        </div>
      `;
    }
    
    // 4. Documentos faltantes
    if (analysis.missing_docs.length > 0) {
      html += `
        <div class="mb-4">
          <h6 class="text-primary">
            <i class="fas fa-file-medical me-2"></i>
            Documentos Nuevos Requeridos (${analysis.missing_docs.length})
          </h6>
          <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            Deberás subir estos documentos después del cambio.
          </div>
          <ul class="list-group">
      `;
      
      analysis.missing_docs.forEach(doc => {
        html += `
          <li class="list-group-item">
            <strong>${doc.name}</strong>
            <div class="small text-muted">${doc.step_name}</div>
            <div class="small text-muted">ID requerido: ${doc.archive_id}</div>
          </li>
        `;
      });
      
      html += `
          </ul>
        </div>
      `;
    }
    
    // 5. Estado de entrevista
    if (analysis.interview_status.has_interview) {
      const willCancel = analysis.interview_status.will_cancel;
      html += `
        <div class="alert ${willCancel ? 'alert-danger' : 'alert-success'} mb-4">
          <h6 class="mb-2">
            <i class="fas fa-calendar-alt me-2"></i>
            Estado de Entrevista
          </h6>
          ${willCancel 
            ? `<p class="mb-0">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Tu entrevista será cancelada.</strong><br>
                Motivo: ${analysis.interview_status.reason}
              </p>`
            : `<p class="mb-0">
                <i class="fas fa-check-circle me-2"></i>
                Tu entrevista se mantendrá activa en el nuevo programa.
              </p>`
          }
        </div>
      `;
    }
    
    // 6. Campo de razón
    html += `
      <div class="mb-3">
        <label class="form-label">
          <strong>Razón del cambio</strong> <span class="text-muted">(opcional)</span>
        </label>
        <textarea class="form-control" id="transferReason" rows="3" 
                  placeholder="Explica brevemente por qué deseas cambiar de programa..."></textarea>
      </div>
    `;
    
    html += '</div>';
    
    container.innerHTML = html;
    document.getElementById('btnConfirmTransfer').disabled = false;
  }
  
  // ==================== EJECUTAR TRANSFERENCIA ====================
  async function executeTransfer() {
    const reason = document.getElementById('transferReason')?.value || '';
    const confirmBtn = document.getElementById('btnConfirmTransfer');
    const originalText = confirmBtn.innerHTML;
    
    // Deshabilitar botón y mostrar loading
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
    
    try {
      const res = await fetch('/api/v1/program-changes/execute', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': getCsrf()
        },
        body: JSON.stringify({
          from_program_id: currentFromProgram.id,
          to_program_id: currentToProgram.id,
          reason: reason
        })
      });
      
      const json = await res.json();
      
      if (!res.ok || !json.ok) {
        throw new Error(json.error || 'Error al ejecutar el cambio');
      }
      
      // Éxito
      bootstrap.Modal.getInstance(document.getElementById('analysisModal')).hide();
      
      flash('Cambio de programa completado exitosamente', 'success');
      
      // Redirigir al nuevo programa después de 2 segundos
      setTimeout(() => {
        window.location.href = `/programs/admission/${currentToProgram.slug}`;
      }, 2000);
      
    } catch (err) {
      console.error('Transfer error:', err);
      flash(`Error: ${err.message}`, 'danger');
      confirmBtn.innerHTML = originalText;
      confirmBtn.disabled = false;
    }
  }
  
})();