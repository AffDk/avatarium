/**
 * Avatarium Client-Side JavaScript
 *
 * Handles: filename validation, drag-and-drop upload, person grouping preview,
 * file size checks, form submission.
 */

// ── Filename Validation ──────────────────────────────────

const FILENAME_REGEX = /^[a-zA-Z0-9]+_\d+\.\w+$/;
const ALLOWED_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function validateFilename(name) {
    if (!FILENAME_REGEX.test(name)) {
        return { valid: false, error: 'Must match <person>_<number>.<ext> format' };
    }
    const ext = name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) {
        return { valid: false, error: `Unsupported extension .${ext}` };
    }
    return { valid: true, person: name.split('_')[0].toLowerCase(), error: null };
}

function parseFilename(name) {
    const match = name.match(/^([a-zA-Z0-9]+)_(\d+)\.(\w+)$/);
    if (!match) return null;
    return {
        person: match[1].toLowerCase(),
        seq: parseInt(match[2], 10),
        ext: match[3].toLowerCase()
    };
}

// ── Token Management ─────────────────────────────────────

function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
}

function getToken() {
    return getCookie('access_token');
}

function authHeaders() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// ── Project Form ─────────────────────────────────────────

const projectForm = document.getElementById('project-form');
const uploadSection = document.getElementById('upload-section');
let currentProjectId = null;

if (projectForm) {
    projectForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('title').value;
        const videoStyle = document.querySelector('input[name="video_style"]:checked').value;

        try {
            const resp = await fetch('/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders()
                },
                body: JSON.stringify({ title, video_style: videoStyle })
            });

            if (resp.ok) {
                const data = await resp.json();
                // Redirect to project detail page for upload & scenario
                window.location.href = `/projects/${data.id}`;
            } else {
                const err = await resp.json();
                alert(err.detail || 'Failed to create project');
            }
        } catch (err) {
            alert('Network error: ' + err.message);
        }
    });
}

// ── File Upload (Drag & Drop + Input) ────────────────────

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const personGroups = document.getElementById('person-groups');
const uploadBtn = document.getElementById('upload-btn');

let selectedFiles = [];

if (dropzone) {
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        handleFiles(Array.from(e.dataTransfer.files));
    });

    // Click opens file picker (but not when clicking browse — handled separately)
    dropzone.addEventListener('click', (e) => {
        if (e.target.id === 'browse-btn') return;
        if (fileInput) fileInput.click();
    });
}

// Browse button (stop propagation to avoid double-trigger from dropzone)
const browseBtn = document.getElementById('browse-btn');
if (browseBtn && fileInput) {
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        handleFiles(Array.from(fileInput.files));
        fileInput.value = ''; // Reset so same files can be re-selected
    });
}

function handleFiles(newFiles) {
    // Accumulate new valid files into selectedFiles
    for (const file of newFiles) {
        const validation = validateFilename(file.name);

        if (!validation.valid) continue;
        if (file.size > MAX_FILE_SIZE) continue;

        const parsed = parseFilename(file.name);
        if (!parsed) continue;

        // Skip duplicates
        if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
            continue;
        }

        selectedFiles.push(file);
    }

    renderPreview();
}

function renderPreview() {
    const groups = {};
    const previewHtml = [];

    for (const file of selectedFiles) {
        const parsed = parseFilename(file.name);
        if (!parsed) continue;
        previewHtml.push(
            `<div class="file-item file-valid">✅ ${file.name} → ${parsed.person} #${parsed.seq}</div>`
        );
        if (!groups[parsed.person]) groups[parsed.person] = [];
        groups[parsed.person].push(file);
    }

    if (filePreview) filePreview.innerHTML = previewHtml.join('');

    if (personGroups) {
        const groupHtml = Object.entries(groups).map(([person, files]) =>
            `<div class="person-group">
                <strong>${person}</strong>: ${files.length} photo(s)
            </div>`
        ).join('');
        personGroups.innerHTML = groupHtml || '';
    }

    if (uploadBtn) {
        uploadBtn.disabled = selectedFiles.length === 0;
    }
}

if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
        if (!currentProjectId || selectedFiles.length === 0) return;

        const formData = new FormData();
        selectedFiles.forEach(file => formData.append('photos', file));

        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading...';

        try {
            const resp = await fetch(`/api/projects/${currentProjectId}/photos`, {
                method: 'POST',
                headers: authHeaders(),
                body: formData
            });

            // Parse response safely
            let body = null;
            try { body = await resp.json(); } catch (e) { /* not JSON */ }

            if (resp.ok) {
                const count = body ? body.uploaded : selectedFiles.length;
                const persons = body && body.persons_created ? body.persons_created.join(', ') : '';
                alert(`Uploaded ${count} photo(s).${persons ? ' Persons: ' + persons : ''}`);
                uploadBtn.textContent = 'Upload More Photos';
                selectedFiles = [];
                renderPreview();
            } else {
                // Handle FastAPI error responses properly
                let errorMsg = 'Upload failed';
                if (body) {
                    if (typeof body.detail === 'string') {
                        errorMsg = body.detail;
                    } else if (Array.isArray(body.detail)) {
                        errorMsg = body.detail.map(e => {
                            const loc = e.loc ? e.loc.join(' → ') : '';
                            return loc ? `${loc}: ${e.msg}` : e.msg;
                        }).join('\n');
                    }
                }
                alert(errorMsg);
            }
        } catch (err) {
            alert('Network error: ' + err.message);
        } finally {
            uploadBtn.disabled = selectedFiles.length === 0;
            if (uploadBtn.textContent === 'Uploading...') {
                uploadBtn.textContent = 'Upload Photos';
            }
        }
    });
}

// ── Scenario Character Count ─────────────────────────────

const scenarioInput = document.getElementById('scenario');
const charCount = document.getElementById('char-count');

if (scenarioInput && charCount) {
    scenarioInput.addEventListener('input', () => {
        charCount.textContent = `${scenarioInput.value.length} / 10000`;
    });
}
