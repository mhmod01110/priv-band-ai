let currentReport = null;
let currentIdempotencyKey = null;
let isProcessing = false;

// 🔍 Debug Helper
function debugLog(message, data = null) {
    const timestamp = new Date().toLocaleTimeString('ar-SA');
    console.log(`[${timestamp}] 🔍 ${message}`, data || '');
}

// ✅ تأكد من إخفاء Loading عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
    debugLog('Page loaded - Hiding loading overlay');
    document.getElementById('loading').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
});

// ✨ Main Form Submit Handler
document.getElementById('analysisForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  debugLog('Form submitted');
  
  if (isProcessing) {
      debugLog('Already processing - ignoring request');
      showWarning('⏳ يرجى الانتظار حتى انتهاء التحليل الحالي');
      return;
  }
  
  const data = {
      shop_name: document.getElementById('shopName').value,
      shop_specialization: document.getElementById('shopSpecialization').value,
      policy_type: document.getElementById('policyType').value,
      policy_text: document.getElementById('policyText').value
  };

  debugLog('Form data collected', data);

  setFormState(true);
  document.getElementById('loading').style.display = 'flex'; // ✅ استخدم flex بدل block
  document.getElementById('errorMessage').style.display = 'none';
  document.getElementById('reportSection').style.display = 'none';

  debugLog('UI prepared - sending request');

  try {
      const { response, cacheStatus, cacheTimestamp, result, returnedKey } = await checkCacheFirst(data, currentIdempotencyKey);
      
      debugLog('Response received', {
          status: response.status,
          cacheStatus,
          cacheTimestamp,
          returnedKey,
          from_cache: result.from_cache,
          success: result.success
      });

      // ✅ تحديث المفتاح الحالي
      if (returnedKey) {
          currentIdempotencyKey = returnedKey;
          debugLog('Idempotency key updated', returnedKey);
      }

      // 🔍 الحالة 1: الطلب قيد التنفيذ (Conflict)
      if (response.status === 409) {
          debugLog('Request in progress (409) - retrying in 3s');
          showWarning('⏳ ' + (result.detail || 'جاري معالجة طلب مشابه...'));
          setTimeout(async () => {
              showInfo('🔄 إعادة المحاولة...');
              await retryRequest(data, currentIdempotencyKey);
          }, 3000);
          return;
      }
      
      // ❌ الحالة 2: خطأ
      if (!response.ok) {
          debugLog('Request failed', { status: response.status, detail: result.detail });
          throw new Error(result.detail || result.message || 'حدث خطأ غير متوقع');
      }
      
      // ✅ الحالة 3: Cache HIT - 🔥 التحقق المحسّن
      const isCacheHit = result.from_cache === true || cacheStatus === 'HIT';
      
      debugLog('Cache check result', {
          isCacheHit,
          from_cache: result.from_cache,
          cacheStatus,
          timestamp: cacheTimestamp
      });

      if (isCacheHit) {
          debugLog('🎯 CACHE HIT - Showing dialog');
          document.getElementById('loading').style.display = 'none';
          showCacheConfirmDialog(result, cacheTimestamp, data);
          return;
      }
      
      // ✅ الحالة 4: نتيجة جديدة (MISS)
      if (result.success) {
          debugLog('✅ New analysis successful');
          currentReport = result;
          displayReport(result);
          showSuccess('✅ تم التحليل بنجاح!');
      } else {
          debugLog('❌ Analysis failed', result.message);
          throw new Error(result.message || 'فشل التحليل');
      }
      
  } catch (error) {
      debugLog('❌ Error caught', error);
      console.error('Analysis Error:', error);
      let errorMsg = error.message;
      if (errorMsg.includes('Failed to fetch') || errorMsg.includes('Network')) {
          errorMsg = '❌ فشل الاتصال بالخادم (Localhost:8000).';
      }
      showError(errorMsg);
      setFormState(false);
      document.getElementById('loading').style.display = 'none';
  } finally {
      // نتأكد أن الـ Dialog غير مفتوح قبل فك القفل
      const isDialogOpen = document.querySelector('.cache-dialog-overlay');
      if (!isDialogOpen && document.getElementById('loading').style.display === 'flex') {
           debugLog('Finally block - unlocking form');
           setFormState(false);
           document.getElementById('loading').style.display = 'none';
      }
  }
});

// ✨ دالة التحقق من الكاش
async function checkCacheFirst(data, idempotencyKey) {
  try {
      debugLog('Checking cache', { hasKey: !!idempotencyKey });
      
      const headers = { 'Content-Type': 'application/json' };
      if (idempotencyKey) {
          headers['X-Idempotency-Key'] = idempotencyKey;
          debugLog('Using existing idempotency key', idempotencyKey.substring(0, 30));
      }

      const response = await fetch('http://localhost:8000/api/analyze', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(data)
      });

      const cacheStatus = response.headers.get('X-Cache-Status');
      const cacheTimestamp = response.headers.get('X-Cache-Timestamp');
      const returnedKey = response.headers.get('X-Idempotency-Key');
      const result = await response.json();

      debugLog('Response headers', {
          'X-Cache-Status': cacheStatus,
          'X-Cache-Timestamp': cacheTimestamp,
          'X-Idempotency-Key': returnedKey ? returnedKey.substring(0, 30) : null
      });

      debugLog('Response body preview', {
          success: result.success,
          from_cache: result.from_cache,
          has_report: !!result.compliance_report
      });

      return { response, cacheStatus, cacheTimestamp, result, returnedKey };
  } catch (error) {
      debugLog('❌ Fetch error', error.message);
      throw error;
  }
}

// ✨ دالة لإجبار تحليل جديد (Force Refresh)
async function forceNewAnalysis(data, oldKey) {
  try {
      debugLog("🚀 Force Refresh Started", { oldKey: oldKey ? oldKey.substring(0, 30) : null });

      const response = await fetch('http://localhost:8000/api/analyze', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-Idempotency-Key': oldKey,
              'X-Force-Refresh': 'true'
          },
          body: JSON.stringify(data)
      });

      const result = await response.json();

      debugLog("Force Refresh response", {
          ok: response.ok,
          status: response.status,
          success: result.success
      });

      if (!response.ok) {
          throw new Error(result.detail || 'فشل التحليل الجديد');
      }

      if (result.success) {
          currentReport = result;
          displayReport(result);
          showSuccess('✅ تم إجراء تحليل جديد وتحديث البيانات!');
      } else {
          showError(result.message);
      }

  } catch (error) {
      debugLog('❌ Force analysis error', error.message);
      console.error('Force Analysis Error:', error);
      showError('حدث خطأ أثناء التحديث: ' + error.message);
  } finally {
      debugLog('Force analysis complete - unlocking UI');
      setFormState(false);
      document.getElementById('loading').style.display = 'none';
  }
}

// ✨ Dialog للتأكيد من استخدام Cache أو طلب جديد
function showCacheConfirmDialog(cachedResult, cacheTimestamp, data) {
  debugLog('📦 Showing cache confirmation dialog');
  
  const overlay = document.createElement('div');
  overlay.className = 'cache-dialog-overlay';
  
  const complianceRatio = cachedResult.compliance_report?.overall_compliance_ratio 
                          ? cachedResult.compliance_report.overall_compliance_ratio.toFixed(1) 
                          : '0.0';

  let displayDate = 'غير محدد';
  if (cacheTimestamp) {
      try {
          displayDate = new Date(cacheTimestamp).toLocaleString('ar-SA', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
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
  
  debugLog('Dialog added to DOM');
  
  // ✅ الخيار 1: استخدام النتيجة المحفوظة
  document.getElementById('useCacheBtn').addEventListener('click', () => {
      debugLog('User chose: Use cached result');
      overlay.remove();
      currentReport = cachedResult;
      displayReport(cachedResult);
      showSuccess('✅ تم عرض النتيجة المحفوظة');
      
      setFormState(false);
      document.getElementById('loading').style.display = 'none';
  });
  
  // 🔥 الخيار 2: إجراء تحليل جديد (Force ReRun)
  document.getElementById('newAnalysisBtn').addEventListener('click', async () => {
      debugLog('User chose: Force new analysis');
      overlay.remove();
      
      document.getElementById('loading').style.display = 'flex';
      showInfo('🔄 جاري إجراء تحليل جديد...');
      
      await forceNewAnalysis(data, currentIdempotencyKey);
  });
}

async function retryRequest(data, idempotencyKey) {
  debugLog('Retrying request', { hasKey: !!idempotencyKey });
  
  try {
      const { response, cacheStatus, cacheTimestamp, result, returnedKey } = await checkCacheFirst(data, idempotencyKey);
      
      if (returnedKey) currentIdempotencyKey = returnedKey;

      const isCacheHit = result.from_cache === true || cacheStatus === 'HIT';

      if (response.ok && result.success) {
          if (isCacheHit) {
              debugLog('Retry: Cache HIT');
              document.getElementById('loading').style.display = 'none';
              showCacheConfirmDialog(result, cacheTimestamp, data);
          } else {
              debugLog('Retry: Fresh result');
              currentReport = result;
              displayReport(result);
              showSuccess('✅ تم التحليل بنجاح!');
          }
      } else if (response.status === 409) {
          debugLog('Retry: Still in progress - retrying again');
          setTimeout(() => retryRequest(data, idempotencyKey), 3000);
      } else {
          debugLog('Retry: Failed', result.message || result.detail);
          showError(result.message || result.detail);
      }
  } catch (error) {
      debugLog('❌ Retry error', error.message);
      showError('فشلت إعادة المحاولة: ' + error.message);
  } finally {
      if (!document.querySelector('.cache-dialog-overlay')) {
          setFormState(false);
          document.getElementById('loading').style.display = 'none';
      }
  }
}

// Helper Functions
function generateIdempotencyKey() {
  return 'idem_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
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
  
  debugLog('Form state changed', { disabled });
}

function showSuccess(message) {
    debugLog('Show success', message);
    const n = document.createElement('div');
    n.className = 'success-notification';
    n.innerHTML = `<i class="fas fa-check-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 4000);
}

function showWarning(message) {
    debugLog('Show warning', message);
    const n = document.createElement('div');
    n.className = 'warning-notification';
    n.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 4000);
}

function showInfo(message) {
    debugLog('Show info', message);
    const n = document.createElement('div');
    n.className = 'info-notification';
    n.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${message}</strong>`;
    document.body.appendChild(n);
    setTimeout(() => { n.remove() }, 3000);
}

function showError(message) {
  debugLog('Show error', message);
  const errorDiv = document.getElementById('errorMessage');
  errorDiv.innerHTML = message.replace(/\n/g, '<br>');
  errorDiv.style.display = 'block';
}

// الدوال المتبقية (displayReport, exportReport, copyImprovedPolicy)
function displayReport(result) {
  debugLog('Displaying report');
  
  const report = result.compliance_report;
  if (!report) {
      showError('لم يتم إنشاء تقرير');
      return;
  }

  const html = `
      <div class="report-header">
          <div class="compliance-score">${report.overall_compliance_ratio.toFixed(1)}%</div>
          <div class="grade">${report.compliance_grade}</div>
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

      ${report.critical_issues.length > 0 ? `
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

      ${report.strengths.length > 0 ? `
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

      ${report.weaknesses.length > 0 ? `
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

      ${report.ambiguities.length > 0 ? `
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

      ${report.recommendations.length > 0 ? `
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

              ${result.improved_policy.improvements_made.length > 0 ? `
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
                                  <div class="before">
                                      <strong>قبل:</strong> "${imp.before}"
                                  </div>
                                  <div class="after">
                                      <strong>بعد:</strong> "${imp.after}"
                                  </div>
                              </div>
                          ` : `
                              <div class="after-only">
                                  <strong>تم إضافة:</strong> "${imp.after}"
                              </div>
                          `}
                      </div>
                  `).join('')}
              </div>
              ` : ''}

              ${result.improved_policy.compliance_enhancements.length > 0 ? `
              <div class="enhancements-list">
                  <h4><i class="fas fa-check-double"></i> تحسينات الامتثال</h4>
                  ${result.improved_policy.compliance_enhancements.map(enh => `
                      <div class="enhancement-item">• ${enh}</div>
                  `).join('')}
              </div>
              ` : ''}

              ${result.improved_policy.key_additions.length > 0 ? `
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
  
  debugLog('Report displayed successfully');
}

function exportReport() {
  if (!currentReport) return;
  
  debugLog('Exporting report');
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