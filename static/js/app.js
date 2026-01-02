/**
 * Main Application Logic
 * Integrates: Form Handling -> API (Celery) -> SSE Monitoring -> Report Rendering
 * Enhanced with comprehensive stage-by-stage feedback and Mismatch Handling
 */

// Global State
let currentReport = null;
let currentIdempotencyKey = null;
let currentTaskMonitor = null;
let isProcessing = false;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
    console.log('✅ Application initialized successfully');
});

// ==========================================
//  1. Form Submission & Task Orchestration
// ==========================================
document.getElementById('analysisForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
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

    if (!validateFormData(formData)) return;

    // UI Setup
    setFormState(true);
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
    document.getElementById('loading').style.display = 'flex';
    
    if (currentTaskMonitor) {
        currentTaskMonitor.stop();
        currentTaskMonitor = null;
    }

    const progressBar = new ProgressBar('loading');

    try {
        // --- Step A: Send POST Request ---
        const headers = { 'Content-Type': 'application/json' };
        if (currentIdempotencyKey) headers['X-Idempotency-Key'] = currentIdempotencyKey;

        showInfo('📤 جاري إرسال الطلب...');

        const response = await fetch('http://localhost:8000/api/analyze', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.message || `Server Error: ${response.status}`);
        }

        const result = await response.json();
        if (result.idempotency_key) currentIdempotencyKey = result.idempotency_key;

        // --- Step B: Handle Synchronous/Cached Result ---
        if (result.status === 'completed' && result.from_cache) {
            console.log('✅ Cache HIT');
            progressBar.complete();
            setTimeout(() => {
                document.getElementById('loading').style.display = 'none';
                if (result.result.success === false) {
                     showPolicyMismatch(result.result);
                } else {
                     showCacheConfirmDialog(result.result, result.result.cache_timestamp, formData);
                }
                setFormState(false);
            }, 500);
            return;
        }

        // --- Step C: Handle Async Task via SSE ---
        if (result.status === 'pending') {
            console.log('🚀 Starting SSE monitoring');
            showInfo('✅ تم الاستلام. جاري بدء التحليل...');
            
            currentTaskMonitor = new TaskMonitor(
                result.task_id,
          
                // 1. Progress Update
                (progress) => progressBar.update(progress),
          
                // 2. Success Completion
                (sseData) => {
                    progressBar.complete();
                    setTimeout(() => {
                        handleTaskSuccess(sseData, formData);
                    }, 1000);
                },

                // 3. Error Handler (Robust)
                (errorDetails) => {
                    console.error("❌ App Level Error:", errorDetails);
                    
                    // Update the Progress Bar with the short message
                    progressBar.error(errorDetails); // Passes object safely now
                    
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        // Show the full detailed error box
                        showGenericError(errorDetails);
                        setFormState(false);
                    }, 1500);
                }
            );
            currentTaskMonitor.start();
        } else {
            throw new Error(`Unexpected task status: ${result.status}`);
        }

    } catch (error) {
        console.error('❌ Request Error:', error);
        document.getElementById('loading').style.display = 'none';
        
        // Convert simple exception to structure for generic handler
        const errorStruct = {
            message: error.message.includes('fetch') ? 'فشل الاتصال بالخادم' : error.message,
            details: error.message.includes('fetch') ? 'تأكد من تشغيل FastAPI على المنفذ 8000' : null,
            type: 'request_error'
        };
        showGenericError(errorStruct);
        setFormState(false);
    }
});

// ==========================================
//  2. Task Success Handler
// ==========================================
function handleTaskSuccess(sseData, formData) {
    document.getElementById('loading').style.display = 'none';
    
    let finalOutput = sseData.result;
    // Unwrap nested result if present
    if (finalOutput && finalOutput.result && (finalOutput.result.compliance_report !== undefined || finalOutput.result.success !== undefined)) {
        finalOutput = finalOutput.result;
    }

    finalOutput.shop_name = formData.shop_name;
    finalOutput.policy_type = formData.policy_type;

    // Handle Logic Mismatch
    if (finalOutput.success === false) {
        showPolicyMismatch(finalOutput);
        setFormState(false);
        return;
    }

    // Handle Success
    if (finalOutput.compliance_report) {
        currentReport = finalOutput;
        displayReport(currentReport);
        const complianceRatio = finalOutput.compliance_report.overall_compliance_ratio || 0;
        showSuccess(`✅ تم التحليل بنجاح! الامتثال: ${complianceRatio.toFixed(1)}%`);
    } else {
        showGenericError({
            message: 'استجابة الخادم غير متوقعة',
            details: 'لا توجد بيانات التقرير في الاستجابة.',
            rawError: JSON.stringify(finalOutput)
        });
    }
    setFormState(false);
}

// ==========================================
//  3. Generic Error Display (Adapts to all types)
// ==========================================
function showGenericError(errorObj) {
    // Default fallback values
    const message = errorObj.message || "حدث خطأ غير معروف";
    const details = errorObj.details || null;
    const type = errorObj.type || "unknown";
    const stages = errorObj.completedStages || [];
    const failedStage = errorObj.failedStage || null;

    // Define icons based on type
    const icons = {
        'quota_exceeded': 'fa-hand-holding-usd',
        'timeout': 'fa-hourglass-end',
        'authentication': 'fa-key',
        'network': 'fa-wifi',
        'server_error': 'fa-server',
        'unknown': 'fa-exclamation-circle'
    };
    const icon = icons[type] || icons['unknown'];

    let html = `
        <div class="error-box" style="border: 1px solid #e74c3c; border-radius: 8px; padding: 20px; background: #fff5f5;">
            <div style="display: flex; align-items: flex-start; gap: 15px;">
                <div style="font-size: 2em; color: #c0392b;"><i class="fas ${icon}"></i></div>
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 10px 0; color: #c0392b;">${message}</h3>
                    
                    ${details ? `<p style="margin: 0 0 15px 0; color: #555; background: #fff; padding: 10px; border-radius: 4px; border: 1px solid #eee;">${details}</p>` : ''}
                    
                    ${failedStage ? `<div style="font-size: 0.9em; color: #7f8c8d; margin-bottom: 5px;"><strong>المرحلة الفاشلة:</strong> ${getStageName(failedStage)}</div>` : ''}
                    
                    ${stages.length > 0 ? `
                        <div style="margin-top: 10px;">
                            <div style="font-size: 0.9em; font-weight: bold; margin-bottom: 5px;">المراحل المكتملة بنجاح:</div>
                            <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                                ${stages.map(s => `<span class="badge badge-success" style="font-size: 0.8em;">✓ ${s.name}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <div style="margin-top: 15px; text-align: left;">
                <button class="btn btn-secondary btn-small" onclick="location.reload()">
                    <i class="fas fa-sync"></i> إعادة المحاولة
                </button>
            </div>
        </div>
    `;

    const errorDiv = document.getElementById('errorMessage');
    errorDiv.innerHTML = html;
    errorDiv.style.display = 'block';
}

// Helper function to get stage name
function getStageName(stageNum) {
  const stageMap = {
      0: 'التهيئة والتحقق',
      1: 'المرحلة 1: التحقق الأولي',
      2: 'المرحلة 2: البحث في الذاكرة المؤقتة',
      3: 'المرحلة 3: تحليل الامتثال',
      4: 'المرحلة 4: التوليد والتحسين',
      5: 'المرحلة 5: الإنهاء'
  };
  return stageMap[stageNum] || `المرحلة ${stageNum}`;
}

// Form data validation
function validateFormData(data) {
  if (!data.shop_name || data.shop_name.trim().length < 2) {
      showError('يُرجى إدخال اسم المتجر (حرفان على الأقل)');
      return false;
  }
  if (!data.policy_text || data.policy_text.trim().length < 50) {
      showError('نص السياسة قصير جداً (الحد الأدنى 50 حرف)');
      return false;
  }
  return true;
}

// ==========================================
//  2. Mismatch Rendering Logic (NEW)
// ==========================================
function showPolicyMismatch(result) {
    console.log('Rendering Mismatch Report', result);

    const reason = result.policy_match?.reason || result.message || "النص لا يتطابق مع نوع السياسة المختار";
    const confidence = result.policy_match?.confidence !== undefined 
        ? Math.round(result.policy_match.confidence) + '%' 
        : 'غير محدد';
    const method = result.policy_match?.method === 'rule_based_stage_0' ? 'القواعد المحلية (سريع)' : 'الذكاء الاصطناعي (دقيق)';

    const html = `
        <div class="report-header" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);">
            <div class="compliance-score" style="color: #c0392b; background: white;">⚠️</div>
            <div class="grade" style="background: rgba(255,255,255,0.2);">عدم تطابق</div>
            <div style="text-align: center; opacity: 1; color: white; margin-top: 10px;">
                ${result.shop_name} - ${result.policy_type}
            </div>
        </div>

        <div class="section">
            <div class="section-title" style="color: #c0392b; border-color: #c0392b;">
                <i class="fas fa-times-circle"></i> نتيجة التحقق من السياسة
            </div>
            <div class="item high">
                <div class="item-title">تم رفض النص المدخل</div>
                <div class="item-content">
                    <p style="font-size: 1.1em; color: #333;"><strong>السبب:</strong> ${reason}</p>
                    <hr style="margin: 10px 0; border: 0; border-top: 1px solid #eee;">
                    <p><strong>نسبة الثقة في الرفض:</strong> ${confidence}</p>
                    <p><strong>طريقة التحقق:</strong> ${method}</p>
                </div>
            </div>
            
            <div class="item">
                <div class="item-content">
                    <i class="fas fa-lightbulb" style="color: #f1c40f;"></i> 
                    <strong>نصيحة:</strong> يرجى التأكد من اختيار نوع السياسة الصحيح (مثل سياسة الخصوصية، الاسترجاع، الشروط والأحكام) ومطابقته للنص المنسوخ.
                </div>
            </div>
        </div>
        
        <div class="export-buttons">
            <button class="btn btn-secondary" onclick="location.reload()">
                <i class="fas fa-sync"></i> محاولة مرة أخرى
            </button>
        </div>
    `;

    document.getElementById('reportContent').innerHTML = html;
    document.getElementById('reportSection').style.display = 'block';
    
    // Scroll to report
    document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth' });
}

// ==========================================
//  3. Success Report Rendering Logic
// ==========================================
function displayReport(result) {
    console.log('Rendering report for:', result.shop_name);
    
    const report = result.compliance_report;
    // Robust check prevents crashing if report is missing
    if (!report) {
        console.error("Missing compliance report in result:", result);
        showError('خطأ في عرض التقرير: البيانات مفقودة');
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

        ${/* Ambiguities */ report.ambiguities && report.ambiguities.length > 0 ? `
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
                    <h4><i class="fas fa-tools"></i> التحسينات المطبقة</h4>
                    ${result.improved_policy.improvements_made.map((imp, idx) => `
                        <div class="improvement-item">
                            <div class="improvement-header">
                                <span class="improvement-number">${idx + 1}</span>
                                <span class="improvement-category">${imp.category}</span>
                            </div>
                            <div class="improvement-desc">${imp.description}</div>
                        </div>
                    `).join('')}
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
//  4. UI Helper Functions & Dialogs
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

function showInfo(message) {
    const n = document.createElement('div');
    n.className = 'info-notification';
    n.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 3000);
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

function showError(msg) {
  const errorDiv = document.getElementById('errorMessage');
  errorDiv.innerHTML = `<div class="error-simple"><i class="fas fa-exclamation-circle"></i> ${msg}</div>`;
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