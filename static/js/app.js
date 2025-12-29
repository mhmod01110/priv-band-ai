/**
 * Main Application Logic
 * Integrates: Form Handling -> API (Celery) -> SSE Monitoring -> Report Rendering
 */

// Global State
let currentReport = null;
let currentIdempotencyKey = null;
let currentTaskMonitor = null;
let isProcessing = false;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
});

// ==========================================
//  1. Form Submission & Task Orchestration
// ==========================================
document.getElementById('analysisForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // A. Validation & Setup
    if (isProcessing) {
        showWarning('⏳ يرجى الانتظار حتى انتهاء التحليل الحالي');
        return;
    }
    
    const formData = {
        shop_name: document.getElementById('shopName').value,
        shop_specialization: document.getElementById('shopSpecialization').value,
        policy_type: document.getElementById('policyType').value,
        policy_text: document.getElementById('policyText').value
    };

    setFormState(true);
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
    document.getElementById('loading').style.display = 'flex';
    
    // Stop any previous monitor to prevent conflicts
    if (currentTaskMonitor) {
        currentTaskMonitor.stop();
        currentTaskMonitor = null;
    }

    const progressBar = new ProgressBar('loading');

    try {
        // B. Submit Analysis Request (POST)
        const headers = { 'Content-Type': 'application/json' };
        if (currentIdempotencyKey) {
            headers['X-Idempotency-Key'] = currentIdempotencyKey;
        }

        const response = await fetch('http://localhost:8000/api/analyze', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // Update idempotency key for next time
        if (result.idempotency_key) {
            currentIdempotencyKey = result.idempotency_key;
        }

        // C. Handle Cache Hit (Immediate Success)
        if (result.status === 'completed' && result.from_cache) {
            progressBar.complete();
            setTimeout(() => {
                document.getElementById('loading').style.display = 'none';
                showCacheConfirmDialog(result.result, result.result.cache_timestamp, formData);
                setFormState(false);
            }, 500);
            return;
        }

        // D. Handle Async Task (Pending -> Stream)
        if (result.status === 'pending') {
            showInfo('🚀 تم إرسال الطلب للمعالجة - جاري الاتصال بخادم التحليل...');
            
            // Start listening to Server-Sent Events
            currentTaskMonitor = new TaskMonitor(
              result.task_id,
          
              // 1. On Progress Update
              (progress) => {
                  progressBar.update(progress);
              },
          
              // 2. On Completion (Success) - FIX HERE
              (sseData) => {
                  console.log("✅ Analysis Completed Raw Data:", sseData);
                  progressBar.complete();
                  
                  setTimeout(() => {
                      document.getElementById('loading').style.display = 'none';
                      
                      // --- FIX: Unwrap the double 'result' ---
                      let finalOutput = sseData.result;
          
                      // Check if the data is nested inside another 'result' key
                      if (finalOutput && finalOutput.result && finalOutput.result.compliance_report) {
                          finalOutput = finalOutput.result;
                      }
          
                      // --- FIX: Inject Form Data (Shop Name) ---
                      // The Celery task might not return the shop name, so we add it from the form
                      // so displayReport can show the title correctly.
                      finalOutput.shop_name = formData.shop_name;
                      finalOutput.policy_type = formData.policy_type;
          
                      if (finalOutput && finalOutput.compliance_report) {
                          currentReport = finalOutput;
                          displayReport(currentReport);
                          showSuccess('✅ تم التحليل بنجاح!');
                      } else {
                          console.error("Structure mismatch. Available keys:", Object.keys(finalOutput || {}));
                          showError('استجابة الخادم غير متوقعة: لا توجد بيانات التقرير.');
                      }
                      
                      setFormState(false);
                  }, 1000);
              },

                // 3. On Error (Failure)
                (errorMessage) => {
                    console.error("Task Error:", errorMessage);
                    progressBar.error('فشل التحليل');
                    
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        showError('حدث خطأ أثناء التحليل: ' + errorMessage);
                        setFormState(false);
                    }, 1500);
                }
            );
            
            currentTaskMonitor.start();
        }

    } catch (error) {
        console.error('Analysis Error:', error);
        document.getElementById('loading').style.display = 'none';
        showError('❌ فشل الاتصال بالخادم: ' + error.message);
        setFormState(false);
    }
});

// ==========================================
//  2. Report Rendering Logic
// ==========================================
function displayReport(result) {
    console.log('Rendering report for:', result.shop_name);
    
    const report = result.compliance_report;
    if (!report) {
        showError('لم يتم إنشاء تقرير (البيانات مفقودة)');
        return;
    }

    const html = `
        <div class="report-header">
            <div class="compliance-score">${report.overall_compliance_ratio ? report.overall_compliance_ratio.toFixed(1) : '0.0'}%</div>
            <div class="grade">${report.compliance_grade || 'N/A'}</div>
            <div style="text-align: center; opacity: 0.9;">
                ${result.shop_name} - ${result.policy_type}
            </div>
        </div>

        <div class="section">
            <div class="section-title">
                <i class="fas fa-info-circle"></i> ملخص التقرير
            </div>
            <div class="item">
                <div class="item-content">${report.summary}</div>
            </div>
        </div>

        ${/* Critical Issues */ report.critical_issues && report.critical_issues.length > 0 ? `
        <div class="section">
            <div class="section-title">
                <i class="fas fa-exclamation-triangle"></i> مخالفات حرجة
                <span class="badge badge-critical">${report.critical_issues.length}</span>
            </div>
            ${report.critical_issues.map((issue, index) => `
                <div class="item critical" id="critical-${index}">
                    <div class="item-title">
                        "${issue.phrase}"
                        <span class="badge badge-${issue.severity}">${issue.severity}</span>
                    </div>
                    <div class="item-content">
                        <p><strong>نسبة الامتثال:</strong> ${issue.compliance_ratio}%</p>
                        <p><strong>الاقتراح:</strong> ${issue.suggestion}</p>
                        <p><strong>المرجع النظامي:</strong> ${issue.legal_reference}</p>
                    </div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${/* Strengths */ report.strengths && report.strengths.length > 0 ? `
        <div class="section">
            <div class="section-title">
                <i class="fas fa-check-circle"></i> نقاط القوة
                <span class="badge badge-success">${report.strengths.length}</span>
            </div>
            ${report.strengths.map(strength => `
                <div class="item strength">
                    <div class="item-title">${strength.requirement}</div>
                    <div class="item-content">
                        <p><strong>الحالة:</strong> ${strength.status} (${strength.compliance_ratio}%)</p>
                        ${strength.found_text ? `<p><strong>النص:</strong> "${strength.found_text}"</p>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${/* Weaknesses */ report.weaknesses && report.weaknesses.length > 0 ? `
        <div class="section">
            <div class="section-title">
                <i class="fas fa-times-circle"></i> نقاط الضعف
                <span class="badge badge-high">${report.weaknesses.length}</span>
            </div>
            ${report.weaknesses.map((weakness, index) => `
                <div class="item high" id="weakness-${index}">
                    <div class="item-title">${weakness.issue}</div>
                    <div class="item-content">
                        <p><strong>النص الحالي:</strong> "${weakness.exact_text}"</p>
                        <p><strong>نسبة الامتثال:</strong> ${weakness.compliance_ratio}%</p>
                        <p><strong>الاقتراح:</strong> ${weakness.suggestion}</p>
                        <p><strong>المرجع النظامي:</strong> ${weakness.legal_reference}</p>
                    </div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${/* Ambiguities / Missing Standards */ report.ambiguities && report.ambiguities.length > 0 ? `
        <div class="section">
            <div class="section-title">
                <i class="fas fa-question-circle"></i> معايير مفقودة
                <span class="badge badge-medium">${report.ambiguities.length}</span>
            </div>
            ${report.ambiguities.map((amb, index) => `
                <div class="item medium" id="ambiguity-${index}">
                    <div class="item-title">
                        ${amb.missing_standard}
                        <span class="badge badge-${amb.importance}">${amb.importance}</span>
                    </div>
                    <div class="item-content">
                        <p><strong>الوصف:</strong> ${amb.description}</p>
                        <p><strong>النص المقترح:</strong> "${amb.suggested_text}"</p>
                    </div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${/* Recommendations */ report.recommendations && report.recommendations.length > 0 ? `
        <div class="section">
            <div class="section-title">
                <i class="fas fa-lightbulb"></i> توصيات عامة
            </div>
            ${report.recommendations.map(rec => `
                <div class="item">
                    <div class="item-content">• ${rec}</div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${/* Improved Policy Section */ result.improved_policy ? `
        <div class="section improved-policy-section">
            <div class="section-title" style="background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); color: white;">
                <i class="fas fa-magic"></i> السياسة المحسّنة
                <span class="badge badge-success">${result.improved_policy.estimated_new_compliance}% امتثال</span>
            </div>
            
            <div class="improved-policy-content">
                <div class="policy-box">
                    <div class="policy-header">
                        <i class="fas fa-file-alt"></i> نص السياسة المحسّنة
                        <button class="btn btn-small" onclick="copyImprovedPolicy()">
                            <i class="fas fa-copy"></i> نسخ
                        </button>
                    </div>
                    <pre id="improvedPolicyText" class="policy-text">${result.improved_policy.improved_policy}</pre>
                </div>

                ${result.improved_policy.improvements_made && result.improved_policy.improvements_made.length > 0 ? `
                <div class="improvements-list">
                    <h4><i class="fas fa-tools"></i> التحسينات المطبقة (${result.improved_policy.improvements_made.length})</h4>
                    ${result.improved_policy.improvements_made.map((imp, idx) => `
                        <div class="improvement-item">
                            <div class="improvement-header">
                                <span class="improvement-number">${idx + 1}</span>
                                <span class="improvement-category">${imp.category}</span>
                            </div>
                            <div class="improvement-desc">${imp.description}</div>
                            ${imp.before ? `
                                <div class="before-after">
                                    <div class="before"><strong>قبل:</strong> "${imp.before}"</div>
                                    <div class="after"><strong>بعد:</strong> "${imp.after}"</div>
                                </div>
                            ` : `
                                <div class="after-only"><strong>تم إضافة:</strong> "${imp.after}"</div>
                            `}
                        </div>
                    `).join('')}
                </div>
                ` : ''}

                ${result.improved_policy.compliance_enhancements && result.improved_policy.compliance_enhancements.length > 0 ? `
                <div class="enhancements-list">
                    <h4><i class="fas fa-check-double"></i> تحسينات الامتثال</h4>
                    ${result.improved_policy.compliance_enhancements.map(enh => `
                        <div class="enhancement-item">• ${enh}</div>
                    `).join('')}
                </div>
                ` : ''}

                ${result.improved_policy.key_additions && result.improved_policy.key_additions.length > 0 ? `
                <div class="additions-list">
                    <h4><i class="fas fa-plus-circle"></i> إضافات رئيسية</h4>
                    ${result.improved_policy.key_additions.map(add => `
                        <div class="addition-item">✓ ${add}</div>
                    `).join('')}
                </div>
                ` : ''}

                ${result.improved_policy.notes ? `
                <div class="notes-box">
                    <h4><i class="fas fa-sticky-note"></i> ملاحظات</h4>
                    <p>${result.improved_policy.notes}</p>
                </div>
                ` : ''}
            </div>
        </div>
        ` : ''}

        <div class="export-buttons">
            <button class="btn" onclick="exportReport()">
                <i class="fas fa-download"></i> تصدير التقرير (JSON)
            </button>
            <button class="btn" onclick="window.print()">
                <i class="fas fa-print"></i> طباعة التقرير
            </button>
        </div>
    `;

    document.getElementById('reportContent').innerHTML = html;
    document.getElementById('reportSection').style.display = 'block';
}

// ==========================================
//  3. UI Helper Functions & Dialogs
// ==========================================

function showCacheConfirmDialog(cachedResult, cacheTimestamp, data) {
    const overlay = document.createElement('div');
    overlay.className = 'cache-dialog-overlay';
    
    const complianceRatio = cachedResult.compliance_report?.overall_compliance_ratio 
                            ? cachedResult.compliance_report.overall_compliance_ratio.toFixed(1) 
                            : '0.0';

    let displayDate = 'غير محدد';
    if (cacheTimestamp) {
        try {
            displayDate = new Date(cacheTimestamp).toLocaleString('ar-SA', {
                year: 'numeric', month: 'long', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (e) {
            displayDate = cacheTimestamp;
        }
    }

    const dialog = document.createElement('div');
    dialog.className = 'cache-dialog';
    dialog.innerHTML = `
        <div class="cache-dialog-header">
            <i class="fas fa-database"></i>
            <h3>تم العثور على نتيجة محفوظة</h3>
        </div>
        <div class="cache-dialog-body">
            <div class="cache-info">
                <i class="fas fa-clock"></i>
                <div><strong>تاريخ التحليل:</strong><br>${displayDate}</div>
            </div>
            <div class="cache-info">
                <i class="fas fa-check-circle"></i>
                <div><strong>الامتثال:</strong><br>${complianceRatio}%</div>
            </div>
            <p class="cache-note"><i class="fas fa-lightbulb"></i> النتيجة المحفوظة جاهزة فوراً</p>
        </div>
        <div class="cache-dialog-footer">
            <button class="btn btn-primary" id="useCacheBtn">
                <i class="fas fa-bolt"></i> عرض النتيجة المحفوظة
            </button>
            <button class="btn btn-secondary" id="newAnalysisBtn">
                <i class="fas fa-sync-alt"></i> تحليل جديد (تحديث)
            </button>
        </div>
    `;
    
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    
    document.getElementById('useCacheBtn').addEventListener('click', () => {
        overlay.remove();
        currentReport = cachedResult;
        displayReport(cachedResult);
        showSuccess('✅ تم عرض النتيجة المحفوظة');
        setFormState(false);
    });
    
    document.getElementById('newAnalysisBtn').addEventListener('click', () => {
        overlay.remove();
        showInfo('🔄 جاري إجراء تحليل جديد...');
        
        // Re-submit with header injection? No, we just re-trigger submit with a force refresh flag logic ideally,
        // but for now, we just dispatch submit again.
        // To force refresh, ideally add a hidden input or modify the logic.
        // Assuming your backend handles forced refresh via header, we would need to pass that.
        // For simplicity here, we just re-trigger the form.
        
        // To truly force refresh, we should ideally set a flag:
        // const headers = { 'X-Force-Refresh': 'true' ... } in the main submit logic.
        // But re-triggering is usually enough if the idempotency key logic allows overwrite or we clear it.
        
        // Let's clear the key to force a new one, or rely on API to handle updates.
        currentIdempotencyKey = null; 
        
        const form = document.getElementById('analysisForm');
        const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
        form.dispatchEvent(submitEvent);
    });
}

function setFormState(disabled) {
    isProcessing = disabled;
    const analyzeBtn = document.getElementById('analyzeBtn');
    document.querySelectorAll('#analysisForm input, #analysisForm select, #analysisForm textarea')
        .forEach(input => input.disabled = disabled);
    
    analyzeBtn.disabled = disabled;
    analyzeBtn.innerHTML = disabled 
        ? '<i class="fas fa-spinner fa-spin"></i> جاري التحليل...' 
        : '<i class="fas fa-search"></i> تحليل السياسة';
}

function showSuccess(message) {
    const n = document.createElement('div');
    n.className = 'success-notification';
    n.innerHTML = `<i class="fas fa-check-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 4000);
}

function showWarning(message) {
    const n = document.createElement('div');
    n.className = 'warning-notification';
    n.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 4000);
}

function showInfo(message) {
    const n = document.createElement('div');
    n.className = 'info-notification';
    n.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 3000);
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.innerHTML = message.replace(/\n/g, '<br>');
    errorDiv.style.display = 'block';
}

function exportReport() {
    if (!currentReport) return;
    const dataStr = JSON.stringify(currentReport, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `compliance_report_${Date.now()}.json`;
    link.click();
}

function copyImprovedPolicy() {
    const policyText = document.getElementById('improvedPolicyText').textContent;
    navigator.clipboard.writeText(policyText).then(() => {
        showSuccess('✅ تم نسخ السياسة المحسّنة!');
    }).catch(err => {
        showError('❌ فشل النسخ: ' + err);
    });
}