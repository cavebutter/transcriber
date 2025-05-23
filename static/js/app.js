// Main application JavaScript for RealRecap

// Global app configuration
const App = {
    config: {
        refreshInterval: 5000, // 5 seconds
        maxFileSize: 500 * 1024 * 1024, // 500MB for audio
        maxTranscriptSize: 50 * 1024 * 1024, // 50MB for transcripts
        supportedAudioFormats: ['wav', 'mp3', 'm4a', 'mp4', 'flac', 'ogg'],
        supportedTranscriptFormats: ['txt', 'docx']
    },

    // Utility functions
    utils: {
        formatFileSize: function(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },

        formatTime: function(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);

            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
                return `${minutes}:${secs.toString().padStart(2, '0')}`;
            }
        },

        getFileExtension: function(filename) {
            return filename.split('.').pop().toLowerCase();
        },

        validateFileType: function(file, allowedFormats) {
            const extension = this.getFileExtension(file.name);
            return allowedFormats.includes(extension);
        },

        validateFileSize: function(file, maxSize) {
            return file.size <= maxSize;
        },

        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    },

    // UI components
    ui: {
        showAlert: function(message, type = 'info', duration = 5000) {
            const alertContainer = document.querySelector('.container');
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type} alert-dismissible fade show mt-3`;
            alertDiv.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;

            alertContainer.insertBefore(alertDiv, alertContainer.firstChild);

            // Auto-dismiss after duration
            if (duration > 0) {
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.remove();
                    }
                }, duration);
            }
        },

        updateProgressBar: function(element, percent, message = '') {
            const progressBar = element.querySelector('.progress-bar');
            const progressText = element.querySelector('.progress-text');

            if (progressBar) {
                progressBar.style.width = percent + '%';
                progressBar.setAttribute('aria-valuenow', percent);
                progressBar.textContent = percent + '%';
            }

            if (progressText && message) {
                progressText.textContent = message;
            }
        },

        showModal: function(modalId) {
            const modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
            return modal;
        },

        hideModal: function(modalId) {
            const modalElement = document.getElementById(modalId);
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
        }
    },

    // API functions
    api: {
        get: function(url) {
            return fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                }
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            });
        },

        post: function(url, data) {
            return fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(data)
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            });
        },

        getCSRFToken: function() {
            const token = document.querySelector('meta[name=csrf-token]');
            return token ? token.getAttribute('content') : '';
        },

        getJobStatus: function(jobId) {
            return this.get(`/api/job/${jobId}/status`);
        },

        cancelJob: function(jobId) {
            return this.post(`/api/job/${jobId}/cancel`, {});
        },

        getSystemHealth: function() {
            return this.get('/api/system/health');
        }
    },

    // File upload handling
    upload: {
        setupDragAndDrop: function(uploadArea, fileInput, onFileSelected) {
            uploadArea.addEventListener('click', () => fileInput.click());

            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');

                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    if (onFileSelected) {
                        onFileSelected(files[0]);
                    }
                }
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0 && onFileSelected) {
                    onFileSelected(e.target.files[0]);
                }
            });
        },

        validateFile: function(file, type) {
            const config = App.config;
            let allowedFormats, maxSize;

            if (type === 'audio') {
                allowedFormats = config.supportedAudioFormats;
                maxSize = config.maxFileSize;
            } else if (type === 'transcript') {
                allowedFormats = config.supportedTranscriptFormats;
                maxSize = config.maxTranscriptSize;
            } else {
                return { valid: false, error: 'Unknown file type' };
            }

            if (!App.utils.validateFileType(file, allowedFormats)) {
                return {
                    valid: false,
                    error: `Invalid file format. Supported formats: ${allowedFormats.join(', ').toUpperCase()}`
                };
            }

            if (!App.utils.validateFileSize(file, maxSize)) {
                return {
                    valid: false,
                    error: `File too large. Maximum size: ${App.utils.formatFileSize(maxSize)}`
                };
            }

            return { valid: true };
        },

        updateFileDisplay: function(uploadArea, file) {
            const placeholder = uploadArea.querySelector('.upload-placeholder');
            const uploadInfo = uploadArea.querySelector('.upload-info');
            const filename = uploadInfo.querySelector('.filename');
            const filesize = uploadInfo.querySelector('.filesize');

            filename.textContent = file.name;
            filesize.textContent = App.utils.formatFileSize(file.size);

            placeholder.style.display = 'none';
            uploadInfo.style.display = 'block';
        }
    },

    // Job management
    jobs: {
        refreshTimers: new Map(),

        startStatusUpdates: function(jobId, callback) {
            const timer = setInterval(() => {
                App.api.getJobStatus(jobId)
                    .then(callback)
                    .catch(error => {
                        console.error('Error fetching job status:', error);
                    });
            }, App.config.refreshInterval);

            this.refreshTimers.set(jobId, timer);

            // Initial update
            App.api.getJobStatus(jobId).then(callback).catch(console.error);
        },

        stopStatusUpdates: function(jobId) {
            const timer = this.refreshTimers.get(jobId);
            if (timer) {
                clearInterval(timer);
                this.refreshTimers.delete(jobId);
            }
        },

        stopAllUpdates: function() {
            this.refreshTimers.forEach((timer, jobId) => {
                clearInterval(timer);
            });
            this.refreshTimers.clear();
        },

        getStatusBadgeHTML: function(status) {
            const badges = {
                pending: '<span class="badge bg-warning"><i class="bi bi-clock me-1"></i>Pending</span>',
                processing: '<span class="badge bg-primary"><i class="bi bi-gear-fill me-1 spin"></i>Processing</span>',
                completed: '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Completed</span>',
                failed: '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Failed</span>'
            };
            return badges[status] || badges.pending;
        }
    },

    // Initialization
    init: function() {
        // Set up CSRF token for AJAX requests
        const csrfToken = document.querySelector('meta[name=csrf-token]');
        if (csrfToken) {
            // Already handled in API functions
        }

        // Set up global error handling
        window.addEventListener('error', function(e) {
            console.error('Global error:', e.error);
        });

        // Set up visibility change handling
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                App.jobs.stopAllUpdates();
            } else {
                // Restart updates if on job status page
                const jobId = document.body.dataset.jobId;
                if (jobId) {
                    App.pages.jobStatus.startUpdates(jobId);
                }
            }
        });

        // Initialize page-specific functionality
        this.initPageSpecific();
    },

    initPageSpecific: function() {
        const path = window.location.pathname;

        if (path.includes('/upload/audio')) {
            this.pages.uploadAudio.init();
        } else if (path.includes('/upload/transcript')) {
            this.pages.uploadTranscript.init();
        } else if (path.includes('/job/')) {
            this.pages.jobStatus.init();
        } else if (path.includes('/dashboard')) {
            this.pages.dashboard.init();
        }
    },

    // Page-specific functionality
    pages: {
        uploadAudio: {
            init: function() {
                const uploadArea = document.getElementById('upload-area');
                const fileInput = document.getElementById('audioFile');
                const submitBtn = document.getElementById('submit-btn');
                const diarizationCheck = document.getElementById('enable_diarization');
                const speakerOptions = document.getElementById('speaker-options');

                if (uploadArea && fileInput) {
                    App.upload.setupDragAndDrop(uploadArea, fileInput, (file) => {
                        const validation = App.upload.validateFile(file, 'audio');
                        if (validation.valid) {
                            App.upload.updateFileDisplay(uploadArea, file);
                            if (submitBtn) submitBtn.disabled = false;
                        } else {
                            App.ui.showAlert(validation.error, 'danger');
                        }
                    });
                }

                // Toggle speaker options
                if (diarizationCheck && speakerOptions) {
                    const toggleSpeakerOptions = () => {
                        speakerOptions.style.display = diarizationCheck.checked ? 'block' : 'none';
                    };
                    diarizationCheck.addEventListener('change', toggleSpeakerOptions);
                    toggleSpeakerOptions();
                }
            }
        },

        uploadTranscript: {
            init: function() {
                const uploadArea = document.getElementById('upload-area');
                const fileInput = document.getElementById('transcriptFile');
                const submitBtn = document.getElementById('submit-btn');

                if (uploadArea && fileInput) {
                    App.upload.setupDragAndDrop(uploadArea, fileInput, (file) => {
                        const validation = App.upload.validateFile(file, 'transcript');
                        if (validation.valid) {
                            App.upload.updateFileDisplay(uploadArea, file);
                            if (submitBtn) submitBtn.disabled = false;
                        } else {
                            App.ui.showAlert(validation.error, 'danger');
                        }
                    });
                }
            }
        },

        jobStatus: {
            init: function() {
                const jobIdMatch = window.location.pathname.match(/\/job\/(\d+)/);
                if (jobIdMatch) {
                    const jobId = parseInt(jobIdMatch[1]);
                    this.startUpdates(jobId);
                }
            },

            startUpdates: function(jobId) {
                App.jobs.startStatusUpdates(jobId, (data) => {
                    this.updateStatusDisplay(data);

                    // Stop updates when job is complete or failed
                    if (['completed', 'failed'].includes(data.status)) {
                        App.jobs.stopStatusUpdates(jobId);
                    }
                });
            },

            updateStatusDisplay: function(data) {
                // Update status badge
                const statusBadge = document.getElementById('status-badge');
                if (statusBadge) {
                    statusBadge.innerHTML = App.jobs.getStatusBadgeHTML(data.status);
                }

                // Update progress
                const progressBar = document.getElementById('progress-bar');
                const progressMessage = document.getElementById('progress-message');

                if (progressBar) {
                    progressBar.style.width = data.progress_percent + '%';
                    progressBar.textContent = data.progress_percent + '%';
                }

                if (progressMessage) {
                    progressMessage.textContent = data.progress_message || 'Processing...';
                }

                // Show results when completed
                if (data.status === 'completed' && data.can_download && data.output_files.length > 0) {
                    this.showResults(data.output_files, data.job_id);
                }

                // Show error if failed
                if (data.error_message) {
                    this.showError(data.error_message);
                }
            },

            showResults: function(outputFiles, jobId) {
                const resultsCard = document.getElementById('results-card');
                const downloadFiles = document.getElementById('download-files');

                if (resultsCard && downloadFiles) {
                    downloadFiles.innerHTML = '';

                    outputFiles.forEach(file => {
                        const link = document.createElement('a');
                        link.href = `/download/${jobId}/${file.filename}`;
                        link.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                        link.innerHTML = `
                            <div>
                                <i class="bi bi-file-earmark me-2"></i>
                                <strong>${file.filename}</strong>
                                <br>
                                <small class="text-muted">${file.size_human}</small>
                            </div>
                            <i class="bi bi-download"></i>
                        `;
                        downloadFiles.appendChild(link);
                    });

                    resultsCard.style.display = 'block';
                }
            },

            showError: function(errorMessage) {
                const progressCard = document.getElementById('progress-card');
                if (progressCard) {
                    let errorDiv = document.getElementById('error-message');
                    if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.id = 'error-message';
                        errorDiv.className = 'alert alert-danger mt-3';
                        progressCard.querySelector('.card-body').appendChild(errorDiv);
                    }
                    errorDiv.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i><strong>Error:</strong> ${errorMessage}`;
                }
            }
        },

        dashboard: {
            init: function() {
                // Set up auto-refresh for dashboard
                this.startJobUpdates();
            },

            startJobUpdates: function() {
                const jobRows = document.querySelectorAll('.job-row');
                jobRows.forEach(row => {
                    const jobId = parseInt(row.dataset.jobId);
                    const status = row.querySelector('.status-container .badge').textContent.toLowerCase();

                    if (status.includes('pending') || status.includes('processing')) {
                        App.jobs.startStatusUpdates(jobId, (data) => {
                            this.updateJobRow(row, data);
                        });
                    }
                });
            },

            updateJobRow: function(row, data) {
                const statusContainer = row.querySelector('.status-container');
                if (statusContainer) {
                    statusContainer.innerHTML = App.jobs.getStatusBadgeHTML(data.status);
                }

                // Reload page when job completes for download buttons
                if (['completed', 'failed'].includes(data.status)) {
                    setTimeout(() => location.reload(), 2000);
                }
            }
        }
    }
};

// Global functions for use in templates
window.cancelJob = function(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) {
        return;
    }

    App.api.cancelJob(jobId)
        .then(data => {
            if (data.error) {
                App.ui.showAlert('Error: ' + data.error, 'danger');
            } else {
                App.ui.showAlert('Job cancelled successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            }
        })
        .catch(error => {
            console.error('Error cancelling job:', error);
            App.ui.showAlert('Failed to cancel job', 'danger');
        });
};

window.showDownloads = function(jobId) {
    App.api.getJobStatus(jobId)
        .then(data => {
            const modalBody = document.getElementById('downloadModalBody');

            if (data.output_files && data.output_files.length > 0) {
                let html = '<div class="list-group">';

                data.output_files.forEach(file => {
                    html += `
                        <a href="/download/${jobId}/${file.filename}" 
                           class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div>
                                <i class="bi bi-file-earmark me-2"></i>
                                <strong>${file.filename}</strong>
                                <br>
                                <small class="text-muted">${file.size_human}</small>
                            </div>
                            <i class="bi bi-download"></i>
                        </a>
                    `;
                });

                html += '</div>';
                modalBody.innerHTML = html;
            } else {
                modalBody.innerHTML = '<p class="text-muted">No files available for download.</p>';
            }

            App.ui.showModal('downloadModal');
        })
        .catch(error => {
            console.error('Error loading download files:', error);
            App.ui.showAlert('Failed to load download files', 'danger');
        });
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    App.init();
});

// Cleanup when page unloads
window.addEventListener('beforeunload', function() {
    App.jobs.stopAllUpdates();
});