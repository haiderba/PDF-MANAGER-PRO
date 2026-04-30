let pdfData = {};
let currentFilename = null;
let currentPageIndex = 0;
let cropper = null;

// DOM Elements
const uploadInput = document.getElementById('pdf-upload');
const pdfList = document.getElementById('pdf-list');
const fileCount = document.getElementById('file-count');
const pageToggles = document.getElementById('page-toggles');
const btnApplyAll = document.getElementById('btn-apply-all');
const btnApplyType = document.getElementById('btn-apply-type');
const btnExport = document.getElementById('btn-export');
const emptyState = document.getElementById('empty-state');
const cropperWrapper = document.getElementById('cropper-wrapper');
const imagePreview = document.getElementById('image-preview');
const settingsForm = document.getElementById('settings-form');
const labelCurrentFilename = document.getElementById('current-filename');
const labelCurrentPage = document.getElementById('current-page-label');
const selectDocType = document.getElementById('doc-type');
const inputCustomName = document.getElementById('custom-name');
const statusMessage = document.getElementById('status-message');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');

// New Mode Elements
const radioCropModes = document.querySelectorAll('input[name="crop-mode"]');
const documentSettings = document.getElementById('document-settings');
const profileSettings = document.getElementById('profile-settings');
let currentCropMode = 'document';

// Handle Crop Mode Switch
radioCropModes.forEach(radio => {
    radio.addEventListener('change', (e) => {
        currentCropMode = e.target.value;
        if (currentCropMode === 'document') {
            documentSettings.style.display = 'block';
            profileSettings.style.display = 'none';
        } else {
            documentSettings.style.display = 'none';
            profileSettings.style.display = 'block';
        }
        if (currentFilename) {
            selectPage(currentPageIndex); // Reload cropper with correct mode box
        }
    });
});

// Handle Upload
uploadInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    if (files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files[]', files[i]);
    }

    showLoading(`Uploading and analyzing ${files.length} PDFs... (This may take a moment for OCR)`);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');
        
        const data = await response.json();
        
        // Merge with existing data
        pdfData = { ...pdfData, ...data.pdfs };
        
        renderPdfList();
        updateStatus(`Successfully processed ${Object.keys(data.pdfs).length} PDFs.`);
        
        if (!currentFilename && Object.keys(pdfData).length > 0) {
            selectPdf(Object.keys(pdfData)[0]);
        }
        
        btnApplyAll.disabled = false;
        btnExport.disabled = false;
        
        // Trigger background processing for OCR/Classification
        processAsyncClassification(data.pdfs);
        
    } catch (error) {
        updateStatus(`Error: ${error.message}`);
    } finally {
        hideLoading();
        uploadInput.value = ''; // Reset input
    }
});

// Render Sidebar List
function renderPdfList() {
    const filenames = Object.keys(pdfData);
    fileCount.textContent = filenames.length;
    pdfList.innerHTML = '';

    filenames.forEach(filename => {
        const li = document.createElement('li');
        li.className = `pdf-item ${filename === currentFilename ? 'active' : ''}`;
        
        li.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${filename}</span>
        `;
        
        li.addEventListener('click', () => selectPdf(filename));
        pdfList.appendChild(li);
    });
}

// Select a PDF
function selectPdf(filename) {
    currentFilename = filename;
    renderPdfList(); // Update active state
    
    // Render Page Toggles
    const pages = pdfData[filename].pages;
    pageToggles.innerHTML = '';
    
    pages.forEach((page, index) => {
        const btn = document.createElement('button');
        btn.textContent = `Page ${index + 1}`;
        btn.addEventListener('click', () => selectPage(index));
        pageToggles.appendChild(btn);
    });
    
    // Select page (maintain current index if possible)
    if (pages.length > 0) {
        let targetIndex = currentPageIndex < pages.length ? currentPageIndex : 0;
        selectPage(targetIndex);
    } else {
        emptyState.style.display = 'flex';
        cropperWrapper.style.display = 'none';
        settingsForm.style.display = 'none';
    }
}

// Select a Page within the PDF
function selectPage(index) {
    currentPageIndex = index;
    
    // Update active toggle button
    Array.from(pageToggles.children).forEach((btn, i) => {
        if (i === index) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    
    const pageInfo = pdfData[currentFilename].pages[index];
    
    // Update Settings Form
    emptyState.style.display = 'none';
    cropperWrapper.style.display = 'flex';
    settingsForm.style.display = 'block';
    
    labelCurrentFilename.textContent = currentFilename;
    labelCurrentPage.textContent = index + 1;
    selectDocType.value = pageInfo.document_type;
    inputCustomName.value = pageInfo.custom_name;

    loadCropper(pageInfo);
}

// Input listeners to update state
selectDocType.addEventListener('change', (e) => {
    if (currentFilename) {
        const newType = e.target.value;
        pdfData[currentFilename].pages[currentPageIndex].document_type = newType;
        
        // Auto-update custom name
        let baseName = currentFilename.split('.').slice(0, -1).join('.');
        let newCustomName = newType === 'None' ? baseName : `${baseName}_${newType}`;
        pdfData[currentFilename].pages[currentPageIndex].custom_name = newCustomName;
        inputCustomName.value = newCustomName;
    }
});

inputCustomName.addEventListener('input', (e) => {
    if (currentFilename) {
        pdfData[currentFilename].pages[currentPageIndex].custom_name = e.target.value;
    }
});

// Initialize / Update Cropper
function loadCropper(pageInfo) {
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }

    imagePreview.src = pageInfo.url;
    
    imagePreview.onload = () => {
        cropper = new Cropper(imagePreview, {
            viewMode: 1,
            autoCropArea: currentCropMode === 'document' ? 0.8 : 0.2, // Smaller default box for faces
            ready() {
                if (currentCropMode === 'document' && pageInfo.crop_data) {
                    this.cropper.setData(pageInfo.crop_data);
                } else if (currentCropMode === 'profile' && pdfData[currentFilename].profile_crop && pdfData[currentFilename].profile_source_page === currentPageIndex) {
                    this.cropper.setData(pdfData[currentFilename].profile_crop);
                }
            },
            cropend() {
                // Save crop data to state when user stops dragging
                if (currentFilename) {
                    const data = cropper.getData(true);
                    if (currentCropMode === 'document') {
                        pdfData[currentFilename].pages[currentPageIndex].crop_data = data;
                    } else {
                        pdfData[currentFilename].profile_crop = data;
                        pdfData[currentFilename].profile_source_page = currentPageIndex;
                    }
                }
            }
        });
    };
}

// Apply Crop to the current page number across all PDFs
btnApplyAll.addEventListener('click', () => {
    if (currentCropMode === 'profile') {
        alert("Profile photo crops are unique to each person and cannot be bulk-applied.");
        return;
    }
    if (!currentFilename || !cropper) return;
    
    const cropData = cropper.getData(true);
    let count = 0;
    
    for (let filename in pdfData) {
        if (pdfData[filename].pages[currentPageIndex]) {
            pdfData[filename].pages[currentPageIndex].crop_data = { ...cropData };
            count++;
        }
    }
    
    updateStatus(`Applied crop settings to Page ${currentPageIndex + 1} across ${count} PDFs.`);
});

// Apply Document Type to the current page number across all PDFs
btnApplyType.addEventListener('click', () => {
    if (!currentFilename) return;
    
    const targetType = selectDocType.value;
    let count = 0;
    
    for (let filename in pdfData) {
        if (pdfData[filename].pages[currentPageIndex]) {
            pdfData[filename].pages[currentPageIndex].document_type = targetType;
            
            // Auto-update custom name
            let baseName = filename.split('.').slice(0, -1).join('.');
            let newCustomName = targetType === 'None' ? baseName : `${baseName}_${targetType}`;
            pdfData[filename].pages[currentPageIndex].custom_name = newCustomName;
            
            count++;
        }
    }
    
    // Refresh the UI for the current page
    selectPage(currentPageIndex);
    updateStatus(`Applied "${targetType.replace('_', ' ')}" to Page ${currentPageIndex + 1} across ${count} PDFs.`);
});

// Export
btnExport.addEventListener('click', async () => {
    const filenames = Object.keys(pdfData);
    if (filenames.length === 0) return;

    showLoading(`Exporting PDFs to categorized folders...`);

    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(pdfData)
        });

        if (!response.ok) throw new Error('Export failed');
        
        const data = await response.json();
        updateStatus(`Successfully exported documents from ${data.processed.length} PDFs.`);
    } catch (error) {
        updateStatus(`Error: ${error.message}`);
    } finally {
        hideLoading();
    }
});

// Helpers
function showLoading(text) {
    loadingText.textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function updateStatus(msg) {
    statusMessage.textContent = msg;
    statusMessage.style.opacity = 0;
    setTimeout(() => {
        statusMessage.style.opacity = 1;
    }, 100);
}

async function processAsyncClassification(newPdfs) {
    for (const filename in newPdfs) {
        for (let i = 0; i < newPdfs[filename].pages.length; i++) {
            const page = newPdfs[filename].pages[i];
            if (page.document_type === 'Pending') {
                try {
                    const response = await fetch('/api/classify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: page.path })
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        page.document_type = result.document_type;
                        page.crop_data = result.crop_data;
                        
                        // Auto-update custom name
                        let baseName = filename.split('.').slice(0, -1).join('.');
                        page.custom_name = result.document_type === 'None' ? baseName : `${baseName}_${result.document_type}`;
                        
                        // If this page is currently active in UI, update UI
                        if (currentFilename === filename && currentPageIndex === i) {
                            selectDocType.value = page.document_type;
                            inputCustomName.value = page.custom_name;
                            if (currentCropMode === 'document' && page.crop_data && cropper) {
                                cropper.setData(page.crop_data);
                            }
                        }
                    }
                } catch (e) {
                    console.error("Async classification failed for", filename, i, e);
                }
            }
        }
    }
}
