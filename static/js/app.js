/**
 * Main Application Logic - SECURE VERSION
 * ✅ بدون Headers قابلة للاستغلال
 * ✅ idempotency key من الـ Backend
 * ✅ المستخدم يختار: cache أو جديد
 */

// Global State
let currentReport = null;
let currentCachedResponse = null; // لحفظ الـ cached response
let currentRequestData = null; // لحفظ بيانات الـ request
let currentTaskMonitor = null;
let isProcessing = false;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
    console.log('✅ Application initialized successfully (Secure Mode)');
});

// ==========================================
//  1. Form Submission - SECURE
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

    // حفظ بيانات الـ request
    currentRequestData = formData;

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
        // ✅ بدون Headers خالص - آمن 100%
        const headers = { 'Content-Type': 'application/json' };
        
        console.log('📤 Sending secure request (no custom headers)');
        showInfo('📤 جاري إرسال الطلب...');

        const response = await fetch('http://localhost:8000/api/analyze', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            
            // Handle Pydantic validation errors (422)
            if (response.status === 422 && errorData.detail && Array.isArray(errorData.detail)) {
                const errors = errorData.detail.map(err => {
                    const field = err.loc ? err.loc.join(' > ') : 'unknown';
                    return `${field}: ${err.msg}`;
                }).join('\n');
                
                throw new Error(errors);
            }
            
            throw new Error(errorData.detail || errorData.message || `Server Error: ${response.status}`);
        }

        const result = await response.json();
        console.log('📦 Received response:', result);

        // 🎯 السيناريو 1: موجود في الـ cache - يسأل المستخدم
        if (result.status === 'found_existing' && result.ask_user) {
            console.log('✨ Cache found - asking user for decision');
            progressBar.complete();
            setTimeout(() => {
                document.getElementById('loading').style.display = 'none';
                showCacheModal(result);
                setFormState(false);
            }, 500);
            return;
        }

        // السيناريو 2: Immediate result (validation error)
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

        // السيناريو 3: Async task
        if (result.status === 'pending') {
            console.log('🚀 Starting SSE monitoring for task:', result.task_id);
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
                    console.error("❌ SSE Task Error:", errorDetails);
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
        
        if (currentTaskMonitor) {
            currentTaskMonitor.stop();
            currentTaskMonitor = null;
        }
    }
});

// ==========================================
//  2. Cache Modal - NEW
// ==========================================
function showCacheModal(response) {
    currentCachedResponse = response;
    
    const cachedResult = response.result;
    const complianceRatio = cachedResult?.compliance_report?.overall_compliance_ratio 
                            ? cachedResult.compliance_report.overall_compliance_ratio.toFixed(1) 
                            : '0.0';

    let displayDate = 'غير محدد';
    if (response.cached_at) {
        try {
            displayDate = new Date(response.cached_at).toLocaleString('ar-SA', {
                year: 'numeric', month: 'long', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (e) {
            displayDate = response.cached_at;
        }
    }

    const overlay = document.createElement('div');
    overlay.className = 'cache-dialog-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        animation: fadeIn 0.3s ease;
    `;
    
    const dialog = document.createElement('div');
    dialog.className = 'cache-dialog';
    dialog.style.cssText = `
        background: white;
        border-radius: 15px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        animation: slideUp 0.3s ease;
    `;
    
    dialog.innerHTML = `
        <style>
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes slideUp {
                from { transform: translateY(30px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            .cache-dialog-header {
                text-align: center;
                margin-bottom: 25px;
            }
            .cache-dialog-header i {
                font-size: 3em;
                color: #3498db;
                margin-bottom: 15px;
                display: block;
            }
            .cache-dialog-header h3 {
                margin: 0;
                color: #2c3e50;
                font-size: 1.5em;
            }
            .cache-info-box {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }
            .cache-info-item {
                display: flex;
                align-items: center;
                gap: 15px;
                margin: 15px 0;
                padding: 15px;
                background: rgba(255,255,255,0.1);
                border-radius: 8px;
            }
            .cache-info-item i {
                font-size: 2em;
            }
            .cache-buttons {
                display: flex;
                gap: 15px;
                margin-top: 25px;
            }
            .cache-btn {
                flex: 1;
                padding: 15px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1em;
                font-weight: bold;
                transition: all 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }
            .cache-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .cache-btn-primary {
                background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                color: white;
            }
            .cache-btn-secondary {
                background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
                color: white;
            }
        </style>
        
        <div class="cache-dialog-header">
            <i class="fas fa-database"></i>
            <h3>✅ تم العثور على تحليل سابق</h3>
        </div>
        
        <div class="cache-info-box">
            <div class="cache-info-item">
                <i class="fas fa-clock"></i>
                <div>
                    <strong style="display: block; margin-bottom: 5px;">تاريخ التحليل</strong>
                    <span style="opacity: 0.9;">${displayDate}</span>
                </div>
            </div>
            <div class="cache-info-item">
                <i class="fas fa-check-circle"></i>
                <div>
                    <strong style="display: block; margin-bottom: 5px;">نسبة الامتثال</strong>
                    <span style="font-size: 1.3em;">${complianceRatio}%</span>
                </div>
            </div>
        </div>
        
        <p style="text-align: center; color: #7f8c8d; margin: 20px 0;">
            هل تريد استخدام التحليل السابق أم إنشاء تحليل جديد؟
        </p>
        
        <div class="cache-buttons">
            <button class="cache-btn cache-btn-primary" id="useCacheBtn">
                <i class="fas fa-bolt"></i> استخدام السابق (فوري ومجاني)
            </button>
            <button class="cache-btn cache-btn-secondary" id="newAnalysisBtn">
                <i class="fas fa-sync-alt"></i> تحليل جديد
            </button>
        </div>
    `;
    
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    
    // Use cached result
    document.getElementById('useCacheBtn').addEventListener('click', () => {
        overlay.remove();
        currentReport = cachedResult;
        displayReport(cachedResult);
        showSuccess('✅ تم عرض النتيجة المحفوظة (مجاني وفوري!)');
        setFormState(false);
        console.log('✅ User chose cached result');
    });
    
    // Create new analysis
    document.getElementById('newAnalysisBtn').addEventListener('click', async () => {
        overlay.remove();
        
        // Clear UI
        document.getElementById('reportSection').style.display = 'none';
        document.getElementById('errorMessage').style.display = 'none';
        currentReport = null;
        
        showInfo('🔄 جاري إجراء تحليل جديد...');
        console.log('🔄 User chose new analysis');
        
        await createNewAnalysis();
    });
}

// ==========================================
//  3. Force New Analysis - SECURE
// ==========================================
async function createNewAnalysis() {
    setFormState(true);
    document.getElementById('loading').style.display = 'flex';
    
    const progressBar = new ProgressBar('loading');

    try {
        console.log('📤 Sending force-new request...');
        
        const response = await fetch('http://localhost:8000/api/analyze/force-new', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                idempotency_key: currentCachedResponse.idempotency_key,
                shop_name: currentRequestData.shop_name,
                shop_specialization: currentRequestData.shop_specialization,
                policy_type: currentRequestData.policy_type,
                policy_text: currentRequestData.policy_text
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            
            // Handle rate limiting (429)
            if (response.status === 429) {
                progressBar.error('تم تجاوز الحد المسموح');
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                    showStructuredError({
                        message: '⚠️ تم تجاوز الحد المسموح لطلبات التحديث',
                        details: errorData.detail?.message || 'يمكنك طلب تحليل جديد 3 مرات فقط في الساعة',
                        type: 'quota_exceeded',
                        user_action: 'يرجى الانتظار قليلاً قبل المحاولة مرة أخرى، أو استخدام التحليل السابق'
                    });
                    setFormState(false);
                }, 1000);
                return;
            }
            
            throw new Error(errorData.detail?.message || `Server Error: ${response.status}`);
        }

        const result = await response.json();
        console.log('📦 Force-new response:', result);

        if (result.status === 'pending') {
            showInfo('✅ تم البدء في تحليل جديد...');
            
            currentTaskMonitor = new TaskMonitor(
                result.task_id,
                (progress) => progressBar.update(progress),
                (sseData) => {
                    progressBar.complete();
                    setTimeout(() => {
                        handleTaskSuccess(sseData, currentRequestData);
                    }, 1000);
                },
                (errorDetails) => {
                    console.error("❌ Force-new task error:", errorDetails);
                    progressBar.error(errorDetails);
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        showStructuredError(errorDetails);
                        setFormState(false);
                    }, 1500);
                }
            );
            currentTaskMonitor.start();
        }

    } catch (error) {
        console.error('❌ Force-new error:', error);
        
        progressBar.error(error.message);
        setTimeout(() => {
            document.getElementById('loading').style.display = 'none';
            showStructuredError({
                message: 'فشل إنشاء تحليل جديد',
                details: error.message,
                type: 'request_error'
            });
            setFormState(false);
        }, 1000);
    }
}

// ==========================================
//  4. Handle Immediate Results
// ==========================================
function handleImmediateResult(result, formData) {
    // Check if it's a validation error
    if (result.from_cache === false && result.result && result.result.error_type === 'validation_error') {
        showValidationError(result.result);
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
//  5. Task Success Handler
// ==========================================
function handleTaskSuccess(sseData, formData) {
    document.getElementById('loading').style.display = 'none';
    
    let finalOutput = sseData.result;
    // Unwrap nested result if present
    if (finalOutput && finalOutput.result && (finalOutput.result.compliance_report !== undefined || finalOutput.result.success !== undefined)) {
        finalOutput = finalOutput.result;
    }

    // Check for validation errors
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
        showStructuredError({
            message: 'استجابة الخادم غير مكتملة',
            details: 'فشل إنشاء تقرير الامتثال',
            type: 'missing_data'
        });
    }
    setFormState(false);
}

// ==========================================
//  6. Validation Error Display
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
//  7. Structured Error Display
// ==========================================
function showStructuredError(errorObj) {
    const message = errorObj.message || "حدث خطأ غير معروف";
    const details = errorObj.details || null;
    const type = errorObj.type || errorObj.error_type || "unknown";
    const stages = errorObj.completedStages || [];
    const failedStage = errorObj.failedStage || null;
    const userAction = errorObj.user_action || null;

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
                    
                    ${userAction ? `
                        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #f39c12;">
                            <div style="font-weight: bold; margin-bottom: 8px; color: #856404;">
                                <i class="fas fa-hand-point-right"></i> الإجراء المطلوب:
                            </div>
                            <div style="color: #856404; line-height: 1.6;">${userAction}</div>
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
                                <i class="fas fa-check-circle"></i> المراحل المكتملة:
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

                    ${!userAction ? getUserActionGuidance(type) : ''}
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
//  8. User Action Guidance
// ==========================================
function getUserActionGuidance(errorType) {
    const guidance = {
        'quota_exceeded': {
            icon: 'fa-lightbulb',
            title: 'ماذا تفعل الآن:',
            text: 'تم استنفاد حصة الاستخدام. يمكنك المحاولة مرة أخرى بعد ساعة، أو استخدام التحليل السابق إن وُجد.',
            color: '#9b59b6'
        },
        'timeout': {
            icon: 'fa-clock',
            title: 'ماذا تفعل الآن:',
            text: 'استغرق التحليل وقتاً أطول من المتوقع. حاول مرة أخرى بعد دقائق قليلة.',
            color: '#3498db'
        },
        'authentication': {
            icon: 'fa-shield-alt',
            title: 'تنبيه للمسؤول:',
            text: 'هناك مشكلة في المصادقة مع مزود خدمة الذكاء الاصطناعي.',
            color: '#e74c3c'
        },
        'network': {
            icon: 'fa-wifi',
            title: 'تحقق من الاتصال:',
            text: 'فشل الاتصال بالخادم. تأكد من اتصالك بالإنترنت.',
            color: '#16a085'
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
//  9. Policy Mismatch Display
// ==========================================
function showPolicyMismatch(result) {
    const reason = result.policy_match?.reason || result.message || "النص لا يتطابق مع نوع السياسة";
    const confidence = result.policy_match?.confidence !== undefined 
        ? Math.round(result.policy_match.confidence) + '%' 
        : 'غير محدد';

    const html = `
        <div class="report-header" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);">
            <div class="compliance-score" style="color: #c0392b; background: white;">⚠️</div>
            <div class="grade" style="background: rgba(255,255,255,0.2);">عدم تطابق</div>
            <div style="text-align: center; color: white; margin-top: 10px;">
                ${result.shop_name} - ${result.policy_type}
            </div>
        </div>

        <div class="section">
            <div class="section-title" style="color: #c0392b; border-color: #c0392b;">
                <i class="fas fa-times-circle"></i> نتيجة التحقق
            </div>
            <div class="item high">
                <div class="item-title">تم رفض النص المدخل</div>
                <div class="item-content">
                    <p style="font-size: 1.1em;"><strong>السبب:</strong> ${reason}</p>
                    <hr style="margin: 10px 0; border-top: 1px solid #eee;">
                    <p><strong>نسبة الثقة:</strong> ${confidence}</p>
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
//  10. Success Report Display
// ==========================================
function displayReport(result) {
    const report = result.compliance_report;
    if (!report) {
        showStructuredError({
            message: 'خطأ في عرض التقرير',
            details: 'البيانات المطلوبة مفقودة',
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
                <div class="item critical">
                    <div class="item-title">
                        "${issue.phrase}"
                        <span class="badge badge-${issue.severity}">${issue.severity}</span>
                    </div>
                    <div class="item-content">
                        <p><strong>نسبة الامتثال:</strong> ${issue.compliance_ratio}%</p>
                        <p><strong>الاقتراح:</strong> ${issue.suggestion}</p>
                        <p><strong>المرجع:</strong> ${issue.legal_reference}</p>
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
            ${report.weaknesses.map(weakness => `
                <div class="item high">
                    <div class="item-title">${weakness.issue}</div>
                    <div class="item-content">
                        <p><strong>النص الحالي:</strong> "${weakness.exact_text}"</p>
                        <p><strong>نسبة الامتثال:</strong> ${weakness.compliance_ratio}%</p>
                        <p><strong>الاقتراح:</strong> ${weakness.suggestion}</p>
                        <p><strong>المرجع:</strong> ${weakness.legal_reference}</p>
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
            ${report.ambiguities.map(amb => `
                <div class="item medium">
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
            </div>
        </div>
        ` : ''}

        <div class="export-buttons">
            <button class="btn" onclick="exportReport()">
                <i class="fas fa-download"></i> تصدير التقرير
            </button>
            <button class="btn" onclick="window.print()">
                <i class="fas fa-print"></i> طباعة
            </button>
        </div>
    `;

    document.getElementById('reportContent').innerHTML = html;
    document.getElementById('reportSection').style.display = 'block';
    document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth' });
}

// ==========================================
//  11. Helper Functions
// ==========================================
function handleSuccessResult(result, formData) {
    result.shop_name = formData.shop_name;
    result.policy_type = formData.policy_type;
    currentReport = result;
    displayReport(result);
    const ratio = result.compliance_report?.overall_compliance_ratio || 0;
    showSuccess(`✅ تم التحليل بنجاح! الامتثال: ${ratio.toFixed(1)}%`);
}

function getStageName(stageNum) {
    const map = {
        0: 'التهيئة والتحقق',
        1: 'التحقق الأولي',
        2: 'البحث في الذاكرة',
        3: 'تحليل الامتثال',
        4: 'التوليد والتحسين',
        5: 'الإنهاء'
    };
    return map[stageNum] || `المرحلة ${stageNum}`;
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

function setFormState(disabled) {
    isProcessing = disabled;
    const btn = document.getElementById('analyzeBtn');
    document.querySelectorAll('#analysisForm input, #analysisForm select, #analysisForm textarea')
        .forEach(input => input.disabled = disabled);
    
    btn.disabled = disabled;
    btn.innerHTML = disabled 
        ? '<i class="fas fa-spinner fa-spin"></i> جاري التحليل...' 
        : '<i class="fas fa-search"></i> تحليل السياسة';
}

function showInfo(message) {
    const n = document.createElement('div');
    n.className = 'info-notification';
    n.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 3000);
}

function showSuccess(message) {
    const n = document.createElement('div');
    n.className = 'success-notification';
    n.innerHTML = `<i class="fas fa-check-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 4000);
}

function showWarning(message) {
    const n = document.createElement('div');
    n.className = 'warning-notification';
    n.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 4000);
}

function exportReport() {
    if (!currentReport) return;
    const dataStr = JSON.stringify(currentReport, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `compliance_report_${Date.now()}.json`;
    link.click();
}

function copyImprovedPolicy() {
    const text = document.getElementById('improvedPolicyText').textContent;
    navigator.clipboard.writeText(text).then(() => {
        showSuccess('✅ تم نسخ السياسة المحسّنة!');
    });
}