/**
 * CertifyPro - Bulk Certificate Generator
 * Frontend Application Controller
 */

(function () {
  'use strict';

  // State Management
  const state = {
    currentJobId: null,
    pollTimer: null,
    activeTab: 'csv',
    filterStatus: 'all',
    searchTerm: '',
    pageOffset: 0,
    pageLimit: 20,
    totalCertificates: 0,
    certificates: [],
    selectedCsvFile: null,
    cachedPreviewUrl: null,
    cachedModalUrl: null
  };

  // DOM Element Selectors
  const elements = {
    // Header & Health
    healthPill: document.getElementById('system-health-pill'),
    healthText: document.getElementById('system-health-text'),

    // Form Inputs
    jobForm: document.getElementById('job-submission-form'),
    eventNameInput: document.getElementById('input-event-name'),
    issuerNameInput: document.getElementById('input-issuer-name'),
    issueDateInput: document.getElementById('input-issue-date'),
    defaultCourseInput: document.getElementById('input-default-course'),

    // Tabs
    tabBtnCsv: document.getElementById('tab-btn-csv'),
    tabBtnManual: document.getElementById('tab-btn-manual'),
    tabBtnJson: document.getElementById('tab-btn-json'),
    panelCsv: document.getElementById('panel-csv'),
    panelManual: document.getElementById('panel-manual'),
    panelJson: document.getElementById('panel-json'),

    // CSV Dropzone
    csvDropzone: document.getElementById('csv-dropzone'),
    csvFileInput: document.getElementById('csv-file-input'),
    btnBrowseFile: document.getElementById('btn-browse-file'),
    selectedFileDisplay: document.getElementById('selected-file-display'),
    fileNameBadge: document.getElementById('file-name-badge'),

    // Manual Builder
    builderTbody: document.getElementById('builder-tbody'),
    btnAddRecipientRow: document.getElementById('btn-add-recipient-row'),

    // JSON Input
    jsonRecipientsTextarea: document.getElementById('json-recipients-textarea'),

    // Form Buttons
    btnSubmitJob: document.getElementById('btn-submit-job'),
    btnSubmitText: document.getElementById('btn-submit-text'),
    btnSubmitSpinner: document.getElementById('btn-submit-spinner'),
    btnPreviewSample: document.getElementById('btn-preview-sample'),

    // Preview Pane
    previewContainer: document.getElementById('preview-container'),
    previewPlaceholder: document.getElementById('preview-placeholder'),
    previewIframe: document.getElementById('preview-iframe'),
    btnRefreshPreview: document.getElementById('btn-refresh-preview'),
    btnTriggerInitialPreview: document.getElementById('btn-trigger-initial-preview'),

    // Job Dashboard
    dashboardSection: document.getElementById('job-dashboard-section'),
    displayJobId: document.getElementById('display-job-id'),
    displayJobStatusPill: document.getElementById('display-job-status-pill'),
    displayJobMeta: document.getElementById('display-job-meta'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    displayProgressPercent: document.getElementById('display-progress-percent'),
    statTotal: document.getElementById('stat-total-count'),
    statSucceeded: document.getElementById('stat-succeeded-count'),
    statFailed: document.getElementById('stat-failed-count'),
    statPending: document.getElementById('stat-pending-count'),
    btnDownloadAllZip: document.getElementById('btn-download-all-zip'),
    btnRefreshJobStatus: document.getElementById('btn-refresh-job-status'),
    btnStartNewJob: document.getElementById('btn-start-new-job'),

    // Certificates Table
    filterButtons: document.querySelectorAll('[data-filter]'),
    tableSearchInput: document.getElementById('table-search-input'),
    tableTbody: document.getElementById('certificates-table-tbody'),
    paginationInfoText: document.getElementById('pagination-info-text'),
    btnPrevPage: document.getElementById('btn-prev-page'),
    btnNextPage: document.getElementById('btn-next-page'),

    // PDF Modal
    pdfModalOverlay: document.getElementById('pdf-modal-overlay'),
    btnClosePdfModal: document.getElementById('btn-close-pdf-modal'),
    modalPdfIframe: document.getElementById('modal-pdf-iframe'),

    // Toast Container
    toastContainer: document.getElementById('toast-container')
  };

  // Initialize
  function init() {
    // 1. Set today's date
    const today = new Date().toISOString().split('T')[0];
    elements.issueDateInput.value = today;

    // 2. Pre-populate manual builder with 3 demo recipients
    addRecipientRow('Jane Doe', 'jane.doe@example.com', 'Advanced Machine Learning');
    addRecipientRow('John Smith', 'john.smith@example.com', 'Cloud Architecture');
    addRecipientRow('Alex Rivera', 'alex.rivera@example.com', 'Cybersecurity Defense');

    // 3. Pre-populate JSON textarea
    updateJsonFromManual();

    // 4. Attach event listeners
    setupEventListeners();

    // 5. Check health check endpoint
    checkHealth();

    // 6. Generate initial preview
    generateLivePreview();
  }

  // Event Listeners
  function setupEventListeners() {
    // Tab switching
    elements.tabBtnCsv.addEventListener('click', () => switchTab('csv'));
    elements.tabBtnManual.addEventListener('click', () => switchTab('manual'));
    elements.tabBtnJson.addEventListener('click', () => switchTab('json'));

    // CSV File Selection & Drag-and-drop
    elements.btnBrowseFile.addEventListener('click', (e) => {
      e.stopPropagation();
      elements.csvFileInput.click();
    });
    elements.csvDropzone.addEventListener('click', () => elements.csvFileInput.click());
    elements.csvFileInput.addEventListener('change', handleFileSelect);

    ['dragenter', 'dragover'].forEach(name => {
      elements.csvDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        elements.csvDropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      elements.csvDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        elements.csvDropzone.classList.remove('dragover');
      });
    });

    elements.csvDropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileDrop(e.dataTransfer.files[0]);
      }
    });

    // Manual row addition
    elements.btnAddRecipientRow.addEventListener('click', () => {
      const defaultCourse = elements.defaultCourseInput.value.trim();
      addRecipientRow('', '', defaultCourse);
    });

    // Form submission
    elements.jobForm.addEventListener('submit', handleFormSubmit);

    // Live preview buttons
    elements.btnPreviewSample.addEventListener('click', generateLivePreview);
    elements.btnRefreshPreview.addEventListener('click', generateLivePreview);
    elements.btnTriggerInitialPreview.addEventListener('click', generateLivePreview);

    // Dynamic preview update when title or issuer changes (debounced)
    const debouncePreview = debounce(generateLivePreview, 600);
    elements.eventNameInput.addEventListener('input', debouncePreview);
    elements.issuerNameInput.addEventListener('input', debouncePreview);
    elements.issueDateInput.addEventListener('input', debouncePreview);

    // Dashboard controls
    elements.btnDownloadAllZip.addEventListener('click', handleDownloadZip);
    elements.btnRefreshJobStatus.addEventListener('click', () => {
      if (state.currentJobId) pollJobStatus(state.currentJobId);
    });
    elements.btnStartNewJob.addEventListener('click', () => {
      stopPolling();
      elements.dashboardSection.classList.remove('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      showToast('Ready to launch a new batch!', 'info');
    });

    // Table filters
    elements.filterButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        elements.filterButtons.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        state.filterStatus = e.target.getAttribute('data-filter');
        state.pageOffset = 0;
        loadCertificatesTable();
      });
    });

    // Search input
    elements.tableSearchInput.addEventListener('input', debounce((e) => {
      state.searchTerm = e.target.value.trim().toLowerCase();
      renderCertificatesTable(state.certificates);
    }, 250));

    // Pagination buttons
    elements.btnPrevPage.addEventListener('click', () => {
      if (state.pageOffset >= state.pageLimit) {
        state.pageOffset -= state.pageLimit;
        loadCertificatesTable();
      }
    });

    elements.btnNextPage.addEventListener('click', () => {
      if (state.pageOffset + state.pageLimit < state.totalCertificates) {
        state.pageOffset += state.pageLimit;
        loadCertificatesTable();
      }
    });

    // PDF modal
    elements.btnClosePdfModal.addEventListener('click', closePdfModal);
    elements.pdfModalOverlay.addEventListener('click', (e) => {
      if (e.target === elements.pdfModalOverlay) closePdfModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && elements.pdfModalOverlay.classList.contains('active')) {
        closePdfModal();
      }
    });
  }

  // Health Check
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        elements.healthText.textContent = 'Backend Active • SQLite WAL';
      }
    } catch {
      elements.healthPill.style.borderColor = 'var(--status-error)';
      elements.healthText.textContent = 'Backend Offline';
    }
  }

  // Tabs Management
  function switchTab(tabKey) {
    state.activeTab = tabKey;
    [elements.tabBtnCsv, elements.tabBtnManual, elements.tabBtnJson].forEach(btn => btn.classList.remove('active'));
    [elements.panelCsv, elements.panelManual, elements.panelJson].forEach(p => p.style.display = 'none');

    if (tabKey === 'csv') {
      elements.tabBtnCsv.classList.add('active');
      elements.panelCsv.style.display = 'block';
    } else if (tabKey === 'manual') {
      elements.tabBtnManual.classList.add('active');
      elements.panelManual.style.display = 'block';
    } else if (tabKey === 'json') {
      elements.tabBtnJson.classList.add('active');
      elements.panelJson.style.display = 'block';
      updateJsonFromManual();
    }
  }

  // CSV Drag and Drop
  function handleFileDrop(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      showToast('Please select a valid CSV file (.csv)', 'error');
      return;
    }
    state.selectedCsvFile = file;
    displaySelectedFile(file.name, file.size);
  }

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      state.selectedCsvFile = file;
      displaySelectedFile(file.name, file.size);
    }
  }

  function displaySelectedFile(name, size) {
    const sizeKb = Math.round(size / 1024);
    elements.fileNameBadge.textContent = `📄 ${name} (${sizeKb} KB)`;
    elements.selectedFileDisplay.style.display = 'block';
    showToast(`Loaded ${name}`, 'info');
  }

  // Manual Builder Row Management
  function addRecipientRow(name = '', email = '', course = '') {
    const tr = document.createElement('tr');
    tr.className = 'builder-row';
    tr.innerHTML = `
      <td><input type="text" class="form-input builder-name" placeholder="Full Name" value="${escapeHtml(name)}"></td>
      <td><input type="email" class="form-input builder-email" placeholder="email@address.com" value="${escapeHtml(email)}"></td>
      <td><input type="text" class="form-input builder-course" placeholder="Optional Track" value="${escapeHtml(course)}"></td>
      <td><button type="button" class="btn-remove-row" title="Remove recipient">&times;</button></td>
    `;

    tr.querySelector('.btn-remove-row').addEventListener('click', () => {
      tr.remove();
      if (elements.builderTbody.children.length === 0) {
        addRecipientRow();
      }
    });

    elements.builderTbody.appendChild(tr);
  }

  function getManualRecipients() {
    const rows = elements.builderTbody.querySelectorAll('.builder-row');
    const recipients = [];
    rows.forEach(row => {
      const name = row.querySelector('.builder-name').value.trim();
      const email = row.querySelector('.builder-email').value.trim();
      const course = row.querySelector('.builder-course').value.trim();
      if (name || email) {
        recipients.push({
          name: name,
          email: email,
          course_title: course || null
        });
      }
    });
    return recipients;
  }

  function updateJsonFromManual() {
    const list = getManualRecipients();
    elements.jsonRecipientsTextarea.value = JSON.stringify(list, null, 2);
  }

  // Live Preview Generator
  async function generateLivePreview() {
    const eventName = elements.eventNameInput.value.trim() || 'Mastering Advanced Software Architecture';
    const issuerName = elements.issuerNameInput.value.trim() || 'Institute of Software Leadership';
    const issueDate = elements.issueDateInput.value.trim() || new Date().toISOString().split('T')[0];
    
    // Pick first recipient name from manual builder if available
    const manualList = getManualRecipients();
    const sampleRecipient = manualList.length > 0 ? manualList[0].name : 'Jane Doe';
    const sampleCourse = manualList.length > 0 ? manualList[0].course_title : elements.defaultCourseInput.value.trim();

    try {
      const res = await fetch('/api/v1/certificates/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_name: sampleRecipient,
          event_name: eventName,
          issuer_name: issuerName,
          issue_date: issueDate,
          course_title: sampleCourse || null
        })
      });

      if (!res.ok) {
        throw new Error('Failed to generate preview');
      }

      const blob = await res.blob();
      if (state.cachedPreviewUrl) {
        URL.revokeObjectURL(state.cachedPreviewUrl);
      }
      state.cachedPreviewUrl = URL.createObjectURL(blob);

      elements.previewIframe.src = state.cachedPreviewUrl;
      elements.previewPlaceholder.style.display = 'none';
      elements.previewIframe.style.display = 'block';
    } catch (err) {
      console.warn('Live preview error:', err);
    }
  }

  // Job Submission Handler
  async function handleFormSubmit(e) {
    e.preventDefault();

    const eventName = elements.eventNameInput.value.trim();
    const issuerName = elements.issuerNameInput.value.trim();
    const issueDate = elements.issueDateInput.value.trim();

    if (!eventName || !issuerName || !issueDate) {
      showToast('Please fill in Event Title, Issuer Name, and Issue Date.', 'error');
      return;
    }

    setSubmitting(true);

    try {
      let response;
      if (state.activeTab === 'csv') {
        if (!state.selectedCsvFile) {
          throw new Error('Please select or drop a CSV file first.');
        }

        const formData = new FormData();
        formData.append('event_name', eventName);
        formData.append('issuer_name', issuerName);
        formData.append('issue_date', issueDate);
        formData.append('file', state.selectedCsvFile);

        response = await fetch('/api/v1/jobs/upload', {
          method: 'POST',
          body: formData
        });
      } else if (state.activeTab === 'manual') {
        const recipients = getManualRecipients();
        if (recipients.length === 0) {
          throw new Error('Please add at least one recipient with name and email.');
        }

        response = await fetch('/api/v1/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_name: eventName,
            issuer_name: issuerName,
            issue_date: issueDate,
            recipients: recipients
          })
        });
      } else {
        // Raw JSON tab
        let recipients;
        try {
          recipients = JSON.parse(elements.jsonRecipientsTextarea.value.trim() || '[]');
        } catch {
          throw new Error('Invalid JSON format in recipients textarea.');
        }
        if (!Array.isArray(recipients) || recipients.length === 0) {
          throw new Error('JSON recipients must be a non-empty array.');
        }

        response = await fetch('/api/v1/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_name: eventName,
            issuer_name: issuerName,
            issue_date: issueDate,
            recipients: recipients
          })
        });
      }

      const data = await response.json();

      if (!response.ok) {
        const msg = data.error?.message || data.detail || 'Job submission failed.';
        throw new Error(msg);
      }

      // Success! Job Accepted (HTTP 202)
      showToast(`Job queued successfully (${data.total} recipients)!`, 'success');
      startMonitoringJob(data.job_id, eventName, data.total);

    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  }

  function setSubmitting(isSubmitting) {
    elements.btnSubmitJob.disabled = isSubmitting;
    elements.btnSubmitText.textContent = isSubmitting ? 'Submitting Job...' : '🚀 Launch Certificate Generation';
    elements.btnSubmitSpinner.style.display = isSubmitting ? 'inline-block' : 'none';
  }

  // Job Monitoring & Polling
  function startMonitoringJob(jobId, eventName, total) {
    state.currentJobId = jobId;
    state.pageOffset = 0;
    state.filterStatus = 'all';

    // Show Dashboard
    elements.dashboardSection.classList.add('active');
    elements.displayJobId.textContent = jobId.substring(0, 8) + '...';
    elements.displayJobMeta.textContent = `${eventName} • ${total} Recipients`;

    // Reset Counters
    updateStatusPill('queued');
    elements.progressBarFill.style.width = '0%';
    elements.displayProgressPercent.textContent = '0%';
    elements.btnDownloadAllZip.disabled = true;

    // Scroll to dashboard smoothly
    elements.dashboardSection.scrollIntoView({ behavior: 'smooth' });

    // Initial Poll and start loop
    pollJobStatus(jobId);
    stopPolling();
    state.pollTimer = setInterval(() => pollJobStatus(jobId), 1200);
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function pollJobStatus(jobId) {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}`);
      if (!res.ok) return;

      const job = await res.json();

      // Update counters
      elements.statTotal.textContent = job.total;
      elements.statSucceeded.textContent = job.succeeded;
      elements.statFailed.textContent = job.failed;
      elements.statPending.textContent = job.pending;

      // Update Progress
      const pct = Math.min(100, Math.max(0, job.progress_percent));
      elements.progressBarFill.style.width = `${pct}%`;
      elements.displayProgressPercent.textContent = `${pct}%`;

      // Update Status Pill
      updateStatusPill(job.status);

      // Enable ZIP download if at least one generated or failed
      if (job.succeeded > 0 || job.failed > 0) {
        elements.btnDownloadAllZip.disabled = false;
      }

      // Check if finished
      if (['completed', 'completed_with_errors', 'failed'].includes(job.status)) {
        stopPolling();
        if (job.status === 'completed') {
          showToast('All certificates generated successfully!', 'success');
        } else if (job.status === 'completed_with_errors') {
          showToast(`Completed with ${job.failed} failed items. Check failures list.`, 'info');
        } else {
          showToast('Job failed. Check certificate errors.', 'error');
        }
      }

      // Refresh table content
      loadCertificatesTable();

    } catch (err) {
      console.warn('Error polling job status:', err);
    }
  }

  function updateStatusPill(status) {
    const pill = elements.displayJobStatusPill;
    pill.className = `status-pill status-${status}`;
    pill.textContent = status.replace(/_/g, ' ').toUpperCase();
  }

  // Load and Render Certificates Table
  async function loadCertificatesTable() {
    if (!state.currentJobId) return;

    let url = `/api/v1/jobs/${state.currentJobId}/certificates?limit=${state.pageLimit}&offset=${state.pageOffset}`;
    if (state.filterStatus !== 'all') {
      url += `&status=${state.filterStatus}`;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) return;

      const data = await res.json();
      state.totalCertificates = data.total;
      state.certificates = data.items;

      renderCertificatesTable(data.items);
      updatePaginationControls();
    } catch (err) {
      console.warn('Error loading certificates table:', err);
    }
  }

  function renderCertificatesTable(items) {
    const tbody = elements.tableTbody;
    tbody.innerHTML = '';

    // Apply client-side search filter if search term exists
    const filtered = items.filter(item => {
      if (!state.searchTerm) return true;
      return (
        item.recipient_name.toLowerCase().includes(state.searchTerm) ||
        item.recipient_email.toLowerCase().includes(state.searchTerm) ||
        item.certificate_number.toLowerCase().includes(state.searchTerm)
      );
    });

    if (filtered.length === 0) {
      const emptyRow = document.createElement('tr');
      emptyRow.innerHTML = `<td colspan="6" style="text-align: center; color: var(--text-dim); padding: 32px 16px;">
        No certificates match current filter
      </td>`;
      tbody.appendChild(emptyRow);
      return;
    }

    filtered.forEach(item => {
      const tr = document.createElement('tr');
      const safeName = escapeHtml(item.recipient_name);
      const safeEmail = escapeHtml(item.recipient_email);
      const safeCourse = escapeHtml(item.course_title || '—');
      const certNum = escapeHtml(item.certificate_number);

      let statusBadge = `<span class="status-pill status-${item.status}">${item.status.toUpperCase()}</span>`;
      if (item.status === 'failed' && item.error_message) {
        statusBadge += `<br><span class="error-badge" title="${escapeHtml(item.error_message)}">⚠️ ${escapeHtml(item.error_message)}</span>`;
      }

      let actionsHtml = '';
      if (item.status === 'generated') {
        actionsHtml = `
          <button type="button" class="btn btn-secondary btn-sm" onclick="CertifyApp.previewCertificate('${item.id}')">
            👁️ Preview
          </button>
          <a href="/api/v1/certificates/${item.id}/download" class="btn btn-outline-gold btn-sm" download>
            ⬇️ PDF
          </a>
        `;
      } else {
        actionsHtml = `<span class="text-xs text-dim">—</span>`;
      }

      tr.innerHTML = `
        <td style="font-weight: 600;">${safeName}</td>
        <td class="text-muted">${safeEmail}</td>
        <td>${safeCourse}</td>
        <td class="mono-cell">${certNum}</td>
        <td>${statusBadge}</td>
        <td style="text-align: right; white-space: nowrap;">${actionsHtml}</td>
      `;

      tbody.appendChild(tr);
    });
  }

  function updatePaginationControls() {
    const start = state.totalCertificates === 0 ? 0 : state.pageOffset + 1;
    const end = Math.min(state.pageOffset + state.pageLimit, state.totalCertificates);
    elements.paginationInfoText.textContent = `Showing ${start}–${end} of ${state.totalCertificates} certificates`;

    elements.btnPrevPage.disabled = state.pageOffset <= 0;
    elements.btnNextPage.disabled = state.pageOffset + state.pageLimit >= state.totalCertificates;
  }

  // ZIP Download Handler
  function handleDownloadZip() {
    if (!state.currentJobId) return;
    showToast('Starting ZIP archive stream download...', 'info');
    window.location.href = `/api/v1/jobs/${state.currentJobId}/download`;
  }

  // PDF Preview Modal
  function openPdfModal(certificateId) {
    const inlineUrl = `/api/v1/certificates/${certificateId}/download?inline=true`;
    elements.modalPdfIframe.src = inlineUrl;
    elements.pdfModalOverlay.classList.add('active');
  }

  function closePdfModal() {
    elements.pdfModalOverlay.classList.remove('active');
    elements.modalPdfIframe.src = 'about:blank';
  }

  // Toast System
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `<span>${icon}</span><span style="flex:1;">${escapeHtml(message)}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  // Helper Utilities
  function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Global namespace for inline table onclick handler
  window.CertifyApp = {
    previewCertificate: openPdfModal
  };

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
