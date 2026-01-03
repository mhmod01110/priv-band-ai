/**
 * Main Application Logic with Comprehensive Error Handling
 * Handles: Validation Errors, Stage Failures, Missing Data, All Error Types
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

        // Handle immediate results (cache or validation error)
        if (result.status === 'completed') {
            console.log('✅ Immediate result received');
            progressBar.complete();
            setTimeout(() => {
                document.getElementById('loading').style.display = 'none';
                handleImmediateResult(result, formData);
                setFormState(false);
            }, 500);
            return;
        }

        // Handle async task via SSE
        if (result.status === 'pending') {
            console.log('🚀 Starting SSE monitoring');
            showInfo('✅ تم الاستلام. جاري بدء التحليل...');
            
            currentTaskMonitor = new TaskMonitor(
                result.task_id,
                (progress) => progressBar.update(progress),
                (sseData) => {
                    progressBar.complete();
                    setTimeout(() => {
                        handleTaskSuccess(sseData, formData);
                    }, 1000);
                },
                (errorDetails) => {
                    console.error("❌ App Level Error:", errorDetails);
                    progressBar.error(errorDetails);
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        showStructuredError(errorDetails);
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
        
        const errorStruct = {
            message: error.message.includes('fetch') ? 'فشل الاتصال بالخادم' : error.message,
            details: error.message.includes('fetch') ? 'تأكد من تشغيل FastAPI على المنفذ 8000' : null,
            type: 'request_error'
        };
        showStructuredError(errorStruct);
        setFormState(false);
    }
});

// ==========================================
//  2. Handle Immediate Results
// ==========================================
function handleImmediateResult(result, formData) {
    // Check if it's a validation error
    if (result.from_cache === false && result.result && result.result.error_type === 'validation_error') {
        showValidationError(result.result);
        return;
    }

    // Check if it's a cached result
    if (result.from_cache) {
        if (result.result.success === false) {
            showPolicyMismatch(result.result);
        } else {
            showCacheConfirmDialog(result.result, result.result.cache_timestamp, formData);
        }
        return;
    }

    // Handle other immediate results
    if (result.result) {
        if (result.result.success === false) {
            if (result.result.error_type) {
                showStructuredError(result.result);
            } else {
                showPolicyMismatch(result.result);
            }
        } else {
            handleSuccessResult(result.result, formData);
        }
    }
}

// ==========================================
//  3. Task Success Handler
// ==========================================
function handleTaskSuccess(sseData, formData) {
    document.getElementById('loading').style.display = 'none';
    
    let finalOutput = sseData.result;
    // Unwrap nested result if present
    if (finalOutput && finalOutput.result && (finalOutput.result.compliance_report !== undefined || finalOutput.result.success !== undefined)) {
        finalOutput = finalOutput.result;
    }

    // Check for validation errors that somehow got through
    if (finalOutput.error_type === 'validation_error') {
        showValidationError(finalOutput);
        setFormState(false);
        return;
    }

    finalOutput.shop_name = formData.shop_name;
    finalOutput.policy_type = formData.policy_type;

    // Handle logic mismatch
    if (finalOutput.success === false && !finalOutput.error_type) {
        showPolicyMismatch(finalOutput);
        setFormState(false);
        return;
    }

    // Handle success
    if (finalOutput.compliance_report) {
        currentReport = finalOutput;
        displayReport(currentReport);
        const complianceRatio = finalOutput.compliance_report.overall_compliance_ratio || 0;
        showSuccess(`✅ تم التحليل بنجاح! الامتثال: ${complianceRatio.toFixed(1)}%`);
    } else {
        // Missing compliance report
        showStructuredError({
            message: 'استجابة الخادم غير مكتملة',
            details: 'فشل إنشاء تقرير الامتثال. قد يكون هناك خطأ في مرحلة التحليل.',
            type: 'missing_data',
            rawError: JSON.stringify(finalOutput)
        });
    }
    setFormState(false);
}

// ==========================================
//  4. Validation Error Display (Pre-Stage)
// ==========================================
function showValidationError(error) {
    const categoryMessages = {
        'length_error': '📏 خطأ في طول النص',
        'suspicious_content': '⚠️ محتوى مشبوه',
        'blocked_content': '🚫 محتوى محظور',
        'spam_detected': '🔁 تكرار مفرط',
        'invalid_shop_name': '🏪 اسم متجر غير صالح',
        'invalid_specialization': '📋 تخصص غير صالح'
    };

    const categoryIcons = {
        'length_error': 'fa-ruler',
        'suspicious_content': 'fa-exclamation-triangle',
        'blocked_content': 'fa-ban',
        'spam_detected': 'fa-redo-alt',
        'invalid_shop_name': 'fa-store-slash',
        'invalid_specialization': 'fa-times-circle'
    };

    const title = categoryMessages[error.error_category] || '❌ خطأ في التحقق من البيانات';
    const icon = categoryIcons[error.error_category] || 'fa-exclamation-circle';

    const html = `
        <div class="error-box validation-error" style="border: 2px solid #e67e22; border-radius: 12px; padding: 25px; background: linear-gradient(135deg, #fef5f1 0%, #fff8f3 100%);">
            <div style="display: flex; align-items: flex-start; gap: 20px;">
                <div style="font-size: 3em; color: #e67e22;">
                    <i class="fas ${icon}"></i>
                </div>
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 15px 0; color: #d35400; font-size: 1.4em;">${title}</h3>
                    
                    <div style="background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #e67e22;">
                        <div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                            <i class="fas fa-info-circle"></i> التفاصيل:
                        </div>
                        <div style="color: #555; line-height: 1.6;">${error.details}</div>
                    </div>

                    ${error.user_action ? `
                        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #f39c12;">
                            <div style="font-weight: bold; margin-bottom: 8px; color: #856404;">
                                <i class="fas fa-hand-point-right"></i> ماذا تفعل:
                            </div>
                            <div style="color: #856404; line-height: 1.6;">${error.user_action}</div>
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #f0e4d7; text-align: center;">
                <button class="btn btn-secondary btn-small" onclick="location.reload()" style="background: linear-gradient(135deg, #e67e22 0%, #d35400 100%);">
                    <i class="fas fa-sync"></i> المحاولة مرة أخرى
                </button>
            </div>
        </div>
    `;

    const errorDiv = document.getElementById('errorMessage');
    errorDiv.innerHTML = html;
    errorDiv.style.display = 'block';
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ==========================================
//  5. Structured Error Display (All Types)
// ==========================================
function showStructuredError(errorObj) {
    const message = errorObj.message || "حدث خطأ غير معروف";
    const details = errorObj.details || null;
    const type = errorObj.type || errorObj.error_type || "unknown";
    const stages = errorObj.completedStages || [];
    const failedStage = errorObj.failedStage || null;

    const icons = {
        'quota_exceeded': 'fa-hand-holding-usd',
        'timeout': 'fa-hourglass-end',
        'authentication': 'fa-key',
        'network': 'fa-wifi',
        'server_error': 'fa-server',
        'validation_error': 'fa-exclamation-triangle',
        'missing_data': 'fa-database',
        'unknown': 'fa-exclamation-circle'
    };
    const icon = icons[type] || icons['unknown'];

    const typeColors = {
        'quota_exceeded': '#9b59b6',
        'timeout': '#3498db',
        'authentication': '#e74c3c',
        'network': '#16a085',
        'server_error': '#c0392b',
        'validation_error': '#e67e22',
        'missing_data': '#95a5a6',
        'unknown': '#34495e'
    };
    const color = typeColors[type] || typeColors['unknown'];

    let html = `
        <div class="error-box" style="border: 2px solid ${color}; border-radius: 12px; padding: 25px; background: linear-gradient(135deg, #fef5f5 0%, #fff 100%);">
            <div style="display: flex; align-items: flex-start; gap: 20px;">
                <div style="font-size: 3em; color: ${color};">
                    <i class="fas ${icon}"></i>
                </div>
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 15px 0; color: ${color}; font-size: 1.4em;">${message}</h3>
                    
                    ${details ? `
                        <div style="background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid ${color};">
                            <div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                                <i class="fas fa-info-circle"></i> التفاصيل:
                            </div>
                            <div style="color: #555; line-height: 1.6;">${details}</div>
                        </div>
                    ` : ''}
                    
                    ${failedStage ? `
                        <div style="font-size: 0.95em; color: #7f8c8d; margin-bottom: 10px; padding: 10px; background: #ecf0f1; border-radius: 6px;">
                            <strong><i class="fas fa-times"></i> المرحلة الفاشلة:</strong> ${getStageName(failedStage)}
                        </div>
                    ` : ''}
                    
                    ${stages.length > 0 ? `
                        <div style="margin-top: 15px;">
                            <div style="font-size: 0.95em; font-weight: bold; margin-bottom: 10px; color: #27ae60;">
                                <i class="fas fa-check-circle"></i> المراحل المكتملة بنجاح:
                            </div>
                            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                ${stages.map(s => `
                                    <span style="background: #d4edda; color: #155724; padding: 6px 12px; border-radius: 20px; font-size: 0.85em; border: 1px solid #c3e6cb;">
                                        ✓ ${s.name || getStageName(s.stage)}
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${getUserActionGuidance(type)}
                </div>
            </div>
            
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; text-align: center;">
                <button class="btn btn-secondary btn-small" onclick="location.reload()">
                    <i class="fas fa-sync"></i> إعادة المحاولة
                </button>
            </div>
        </div>
    `;

    const errorDiv = document.getElementById('errorMessage');
    errorDiv.innerHTML = html;
    errorDiv.style.display = 'block';
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ==========================================
//  6. User Action Guidance by Error Type
// ==========================================
function getUserActionGuidance(errorType) {
    const guidance = {
        'quota_exceeded': {
            icon: 'fa-lightbulb',
            title: 'ماذا تفعل الآن:',
            text: 'تم استنفاد حصة الاستخدام اليومية لخدمة الذكاء الاصطناعي. يرجى المحاولة مرة أخرى بعد عدة ساعات أو غداً.',
            color: '#9b59b6'
        },
        'timeout': {
            icon: 'fa-clock',
            title: 'ماذا تفعل الآن:',
            text: 'استغرق التحليل وقتاً أطول من المتوقع. قد يكون الخادم مشغولاً. حاول مرة أخرى بعد دقائق قليلة.',
            color: '#3498db'
        },
        'authentication': {
            icon: 'fa-shield-alt',
            title: 'تنبيه للمسؤول:',
            text: 'هناك مشكلة في المصادقة مع مزود خدمة الذكاء الاصطناعي. يرجى التحقق من مفاتيح API في الإعدادات.',
            color: '#e74c3c'
        },
        'network': {
            icon: 'fa-wifi',
            title: 'تحقق من الاتصال:',
            text: 'فشل الاتصال بالخادم. تأكد من اتصالك بالإنترنت وأن الخادم يعمل بشكل صحيح.',
            color: '#16a085'
        },
        'validation_error': {
            icon: 'fa-edit',
            title: 'راجع المدخلات:',
            text: 'يرجى مراجعة البيانات المدخلة والتأكد من صحتها وخلوها من أي محتوى غير ملائم.',
            color: '#e67e22'
        },
        'missing_data': {
            icon: 'fa-database',
            title: 'بيانات ناقصة:',
            text: 'حدث خطأ في معالجة البيانات. يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني.',
            color: '#95a5a6'
        }
    };

    const guide = guidance[errorType];
    if (!guide) return '';

    return `
        <div style="background: ${guide.color}15; padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 4px solid ${guide.color};">
            <div style="font-weight: bold; margin-bottom: 8px; color: ${guide.color};">
                <i class="fas ${guide.icon}"></i> ${guide.title}
            </div>
            <div style="color: #555; line-height: 1.6; font-size: 0.95em;">${guide.text}</div>
        </div>
    `;
}

// ==========================================
//  7. Policy Mismatch Display
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
    document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth' });
}

// ==========================================
//  8. Success Report Display
// ==========================================
function displayReport(result) {
    console.log('Rendering report for:', result.shop_name);
    
    const report = result.compliance_report;
    if (!report) {
        console.error("Missing compliance report in result:", result);
        showStructuredError({
            message: 'خطأ في عرض التقرير',
            details: 'البيانات المطلوبة للتقرير مفقودة',
            type: 'missing_data'
        });
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

        ${report.critical_issues && report.critical_issues.length > 0 ? `
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

        ${report.strengths && report.strengths.length > 0 ? `
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

        ${report.weaknesses && report.weaknesses.length > 0 ? `
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

        ${report.ambiguities && report.ambiguities.length > 0 ? `
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

        ${result.improved_policy ? `
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
    document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth' });
}

// ==========================================
//  9. Helper Functions
// ==========================================
function handleSuccessResult(result, formData) {
    result.shop_name = formData.shop_name;
    result.policy_type = formData.policy_type;
    currentReport = result;
    displayReport(result);
    const complianceRatio = result.compliance_report?.overall_compliance_ratio || 0;
    showSuccess(`✅ تم التحليل بنجاح! الامتثال: ${complianceRatio.toFixed(1)}%`);
}

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

function validateFormData(data) {
    if (!data.shop_name || data.shop_name.trim().length < 2) {
        showStructuredError({
            message: 'خطأ في اسم المتجر',
            details: 'يُرجى إدخال اسم المتجر (حرفان على الأقل)',
            type: 'validation_error'
        });
        return false;
    }
    if (!data.policy_text || data.policy_text.trim().length < 50) {
        showStructuredError({
            message: 'خطأ في نص السياسة',
            details: 'نص السياسة قصير جداً (الحد الأدنى 50 حرف)',
            type: 'validation_error'
        });
        return false;
    }
    return true;
}

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
        showStructuredError({
            message: 'فشل النسخ',
            details: err.toString(),
            type: 'unknown'
        });
    });
}
