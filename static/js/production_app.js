// let currentReport = null;
// let currentIdempotencyKey = null;
// let isProcessing = false;

// // ✅ تأكد من إخفاء Loading عند تحميل الصفحة
// document.addEventListener('DOMContentLoaded', () => {
//     document.getElementById('loading').style.display = 'none';
//     document.getElementById('errorMessage').style.display = 'none';
//     document.getElementById('reportSection').style.display = 'none';
// });

// // ✨ Main Form Submit Handler
// document.getElementById('analysisForm').addEventListener('submit', async (e) => {
//   e.preventDefault();
  
//   if (isProcessing) {
//       showWarning('⏳ يرجى الانتظار حتى انتهاء التحليل الحالي');
//       return;
//   }
  
//   const data = {
//       shop_name: document.getElementById('shopName').value,
//       shop_specialization: document.getElementById('shopSpecialization').value,
//       policy_type: document.getElementById('policyType').value,
//       policy_text: document.getElementById('policyText').value
//   };

//   setFormState(true);
//   document.getElementById('loading').style.display = 'flex';
//   document.getElementById('errorMessage').style.display = 'none';
//   document.getElementById('reportSection').style.display = 'none';

//   try {
//       const { response, cacheStatus, cacheTimestamp, result, returnedKey } = await checkCacheFirst(data, currentIdempotencyKey);
      
//       if (returnedKey) currentIdempotencyKey = returnedKey;

//       // 🔍 الحالة 1: الطلب قيد التنفيذ (Conflict)
//       if (response.status === 409) {
//           showWarning('⏳ ' + (result.detail || 'جاري معالجة طلب مشابه...'));
//           setTimeout(async () => {
//               showInfo('🔄 إعادة المحاولة...');
//               await retryRequest(data, currentIdempotencyKey);
//           }, 3000);
//           return;
//       }
      
//       // ❌ الحالة 2: خطأ
//       if (!response.ok) {
//           throw new Error(result.detail || result.message || 'حدث خطأ غير متوقع');
//       }
      
//       // ✅ الحالة 3: Cache HIT
//       const isCacheHit = result.from_cache === true || cacheStatus === 'HIT';

//       if (isCacheHit) {
//           document.getElementById('loading').style.display = 'none';
//           showCacheConfirmDialog(result, cacheTimestamp, data);
//           return;
//       }
      
//       // ✅ الحالة 4: نتيجة جديدة (MISS)
//       if (result.success) {
//           currentReport = result;
//           displayReport(result);
//           showSuccess('✅ تم التحليل بنجاح!');
//       } else {
//           throw new Error(result.message || 'فشل التحليل');
//       }
      
//   } catch (error) {
//       console.error('Analysis Error:', error);
//       let errorMsg = error.message;
//       if (errorMsg.includes('Failed to fetch') || errorMsg.includes('Network')) {
//           errorMsg = '❌ فشل الاتصال بالخادم (Localhost:8000).';
//       }
//       showError(errorMsg);
//       setFormState(false);
//       document.getElementById('loading').style.display = 'none';
//   } finally {
//       const isDialogOpen = document.querySelector('.cache-dialog-overlay');
//       if (!isDialogOpen && document.getElementById('loading').style.display === 'flex') {
//            setFormState(false);
//            document.getElementById('loading').style.display = 'none';
//       }
//   }
// });

// // ✨ دالة التحقق من الكاش
// async function checkCacheFirst(data, idempotencyKey) {
//   try {
//       const headers = { 'Content-Type': 'application/json' };
//       if (idempotencyKey) headers['X-Idempotency-Key'] = idempotencyKey;

//       const response = await fetch('http://localhost:8000/api/analyze', {
//           method: 'POST',
//           headers: headers,
//           body: JSON.stringify(data)
//       });

//       const cacheStatus = response.headers.get('X-Cache-Status');
//       const cacheTimestamp = response.headers.get('X-Cache-Timestamp');
//       const returnedKey = response.headers.get('X-Idempotency-Key');
//       const result = await response.json();

//       return { response, cacheStatus, cacheTimestamp, result, returnedKey };
//   } catch (error) {
//       throw error;
//   }
// }

// // ✨ دالة لإجبار تحليل جديد (Force Refresh)
// async function forceNewAnalysis(data, oldKey) {
//   try {
//       const response = await fetch('http://localhost:8000/api/analyze', {
//           method: 'POST',
//           headers: {
//               'Content-Type': 'application/json',
//               'X-Idempotency-Key': oldKey,
//               'X-Force-Refresh': 'true'
//           },
//           body: JSON.stringify(data)
//       });

//       const result = await response.json();

//       if (!response.ok) {
//           throw new Error(result.detail || 'فشل التحليل الجديد');
//       }

//       if (result.success) {
//           currentReport = result;
//           displayReport(result);
//           showSuccess('✅ تم إجراء تحليل جديد وتحديث البيانات!');
//       } else {
//           showError(result.message);
//       }

//   } catch (error) {
//       console.error('Force Analysis Error:', error);
//       showError('حدث خطأ أثناء التحديث: ' + error.message);
//   } finally {
//       setFormState(false);
//       document.getElementById('loading').style.display = 'none';
//   }
// }

// // ✨ Dialog للتأكيد من استخدام Cache أو طلب جديد
// function showCacheConfirmDialog(cachedResult, cacheTimestamp, data) {
//   const overlay = document.createElement('div');
//   overlay.className = 'cache-dialog-overlay';
  
//   const complianceRatio = cachedResult.compliance_report?.overall_compliance_ratio 
//                           ? cachedResult.compliance_report.overall_compliance_ratio.toFixed(1) 
//                           : '0.0';

//   let displayDate = 'غير محدد';
//   if (cacheTimestamp) {
//       try {
//           displayDate = new Date(cacheTimestamp).toLocaleString('ar-SA', {
//               year: 'numeric',
//               month: 'long',
//               day: 'numeric',
//               hour: '2-digit',
//               minute: '2-digit'
//           });
//       } catch (e) {
//           displayDate = cacheTimestamp;
//       }
//   }

//   const dialog = document.createElement('div');
//   dialog.className = 'cache-dialog';
//   dialog.innerHTML = `
//       <div class="cache-dialog-header">
//           <i class="fas fa-database"></i>
//           <h3>تم العثور على نتيجة محفوظة</h3>
//       </div>
//       <div class="cache-dialog-body">
//           <div class="cache-info">
//               <i class="fas fa-clock"></i>
//               <div><strong>تاريخ التحليل:</strong><br>${displayDate}</div>
//           </div>
//           <div class="cache-info">
//               <i class="fas fa-check-circle"></i>
//               <div><strong>الامتثال:</strong><br>${complianceRatio}%</div>
//           </div>
//           <p class="cache-note"><i class="fas fa-lightbulb"></i> النتيجة المحفوظة جاهزة فوراً</p>
//       </div>
//       <div class="cache-dialog-footer">
//           <button class="btn btn-primary" id="useCacheBtn">
//               <i class="fas fa-bolt"></i> عرض النتيجة المحفوظة
//           </button>
//           <button class="btn btn-secondary" id="newAnalysisBtn">
//               <i class="fas fa-sync-alt"></i> تحليل جديد (تحديث)
//           </button>
//       </div>
//   `;
  
//   overlay.appendChild(dialog);
//   document.body.appendChild(overlay);
  
//   // ✅ الخيار 1: استخدام النتيجة المحفوظة
//   document.getElementById('useCacheBtn').addEventListener('click', () => {
//       overlay.remove();
//       currentReport = cachedResult;
//       displayReport(cachedResult);
//       showSuccess('✅ تم عرض النتيجة المحفوظة');
      
//       setFormState(false);
//       document.getElementById('loading').style.display = 'none';
//   });
  
//   // 🔥 الخيار 2: إجراء تحليل جديد (Force ReRun)
//   document.getElementById('newAnalysisBtn').addEventListener('click', async () => {
//       overlay.remove();
//       document.getElementById('loading').style.display = 'flex';
//       showInfo('🔄 جاري إجراء تحليل جديد...');
//       await forceNewAnalysis(data, currentIdempotencyKey);
//   });
// }

// async function retryRequest(data, idempotencyKey) {
//   try {
//       const { response, cacheStatus, cacheTimestamp, result, returnedKey } = await checkCacheFirst(data, idempotencyKey);
      
//       if (returnedKey) currentIdempotencyKey = returnedKey;

//       const isCacheHit = result.from_cache === true || cacheStatus === 'HIT';

//       if (response.ok && result.success) {
//           if (isCacheHit) {
//               document.getElementById('loading').style.display = 'none';
//               showCacheConfirmDialog(result, cacheTimestamp, data);
//           } else {
//               currentReport = result;
//               displayReport(result);
//               showSuccess('✅ تم التحليل بنجاح!');
//           }
//       } else if (response.status === 409) {
//           setTimeout(() => retryRequest(data, idempotencyKey), 3000);
//       } else {
//           showError(result.message || result.detail);
//       }
//   } catch (error) {
//       showError('فشلت إعادة المحاولة: ' + error.message);
//   } finally {
//       if (!document.querySelector('.cache-dialog-overlay')) {
//           setFormState(false);
//           document.getElementById('loading').style.display = 'none';
//       }
//   }
// }

// // Helper Functions
// function setFormState(disabled) {
//   isProcessing = disabled;
//   const analyzeBtn = document.getElementById('analyzeBtn');
//   document.querySelectorAll('#analysisForm input, #analysisForm select, #analysisForm textarea')
//       .forEach(input => input.disabled = disabled);
  
//   analyzeBtn.disabled = disabled;
//   analyzeBtn.innerHTML = disabled 
//       ? '<i class="fas fa-spinner fa-spin"></i> جاري التحليل...' 
//       : '<i class="fas fa-search"></i> تحليل السياسة';
// }

// function showSuccess(message) {
//     const n = document.createElement('div');
//     n.className = 'success-notification';
//     n.innerHTML = `<i class="fas fa-check-circle"></i> <strong>${message}</strong>`;
//     document.body.appendChild(n);
//     setTimeout(() => { n.remove() }, 4000);
// }

// function showWarning(message) {
//     const n = document.createElement('div');
//     n.className = 'warning-notification';
//     n.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <strong>${message}</strong>`;
//     document.body.appendChild(n);
//     setTimeout(() => { n.remove() }, 4000);
// }

// function showInfo(message) {
//     const n = document.createElement('div');
//     n.className = 'info-notification';
//     n.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${message}</strong>`;
//     document.body.appendChild(n);
//     setTimeout(() => { n.remove() }, 3000);
// }

// function showError(message) {
//   const errorDiv = document.getElementById('errorMessage');
//   errorDiv.innerHTML = message.replace(/\n/g, '<br>');
//   errorDiv.style.display = 'block';
// }

// function displayReport(result) {
//   const report = result.compliance_report;
//   if (!report) {
//       showError('لم يتم إنشاء تقرير');
//       return;
//   }

//   const html = `
//       <div class="report-header">
//           <div class="compliance-score">${report.overall_compliance_ratio.toFixed(1)}%</div>
//           <div class="grade">${report.compliance_grade}</div>
//           <div style="text-align: center; opacity: 0.9;">
//               ${result.shop_name} - ${result.policy_type}
//           </div>
//       </div>

//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-info-circle"></i> ملخص التقرير
//           </div>
//           <div class="item">
//               <div class="item-content">${report.summary}</div>
//           </div>
//       </div>

//       ${report.critical_issues.length > 0 ? `
//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-exclamation-triangle"></i> مخالفات حرجة
//               <span class="badge badge-critical">${report.critical_issues.length}</span>
//           </div>
//           ${report.critical_issues.map((issue, index) => `
//               <div class="item critical" id="critical-${index}">
//                   <div class="item-title">
//                       "${issue.phrase}"
//                       <span class="badge badge-${issue.severity}">${issue.severity}</span>
//                   </div>
//                   <div class="item-content">
//                       <p><strong>نسبة الامتثال:</strong> ${issue.compliance_ratio}%</p>
//                       <p><strong>الاقتراح:</strong> ${issue.suggestion}</p>
//                       <p><strong>المرجع النظامي:</strong> ${issue.legal_reference}</p>
//                   </div>
//               </div>
//           `).join('')}
//       </div>
//       ` : ''}

//       ${report.strengths.length > 0 ? `
//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-check-circle"></i> نقاط القوة
//               <span class="badge badge-success">${report.strengths.length}</span>
//           </div>
//           ${report.strengths.map(strength => `
//               <div class="item strength">
//                   <div class="item-title">${strength.requirement}</div>
//                   <div class="item-content">
//                       <p><strong>الحالة:</strong> ${strength.status} (${strength.compliance_ratio}%)</p>
//                       ${strength.found_text ? `<p><strong>النص:</strong> "${strength.found_text}"</p>` : ''}
//                   </div>
//               </div>
//           `).join('')}
//       </div>
//       ` : ''}

//       ${report.weaknesses.length > 0 ? `
//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-times-circle"></i> نقاط الضعف
//               <span class="badge badge-high">${report.weaknesses.length}</span>
//           </div>
//           ${report.weaknesses.map((weakness, index) => `
//               <div class="item high" id="weakness-${index}">
//                   <div class="item-title">${weakness.issue}</div>
//                   <div class="item-content">
//                       <p><strong>النص الحالي:</strong> "${weakness.exact_text}"</p>
//                       <p><strong>نسبة الامتثال:</strong> ${weakness.compliance_ratio}%</p>
//                       <p><strong>الاقتراح:</strong> ${weakness.suggestion}</p>
//                       <p><strong>المرجع النظامي:</strong> ${weakness.legal_reference}</p>
//                   </div>
//               </div>
//           `).join('')}
//       </div>
//       ` : ''}

//       ${report.ambiguities.length > 0 ? `
//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-question-circle"></i> معايير مفقودة
//               <span class="badge badge-medium">${report.ambiguities.length}</span>
//           </div>
//           ${report.ambiguities.map((amb, index) => `
//               <div class="item medium" id="ambiguity-${index}">
//                   <div class="item-title">
//                       ${amb.missing_standard}
//                       <span class="badge badge-${amb.importance}">${amb.importance}</span>
//                   </div>
//                   <div class="item-content">
//                       <p><strong>الوصف:</strong> ${amb.description}</p>
//                       <p><strong>النص المقترح:</strong> "${amb.suggested_text}"</p>
//                   </div>
//               </div>
//           `).join('')}
//       </div>
//       ` : ''}

//       ${report.recommendations.length > 0 ? `
//       <div class="section">
//           <div class="section-title">
//               <i class="fas fa-lightbulb"></i> توصيات عامة
//           </div>
//           ${report.recommendations.map(rec => `
//               <div class="item">
//                   <div class="item-content">• ${rec}</div>
//               </div>
//           `).join('')}
//       </div>
//       ` : ''}

//       ${result.improved_policy ? `
//       <div class="section improved-policy-section">
//           <div class="section-title" style="background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); color: white;">
//               <i class="fas fa-magic"></i> السياسة المحسّنة
//               <span class="badge badge-success">${result.improved_policy.estimated_new_compliance}% امتثال</span>
//           </div>
          
//           <div class="improved-policy-content">
//               <div class="policy-box">
//                   <div class="policy-header">
//                       <i class="fas fa-file-alt"></i> نص السياسة المحسّنة
//                       <button class="btn btn-small" onclick="copyImprovedPolicy()">
//                           <i class="fas fa-copy"></i> نسخ
//                       </button>
//                   </div>
//                   <pre id="improvedPolicyText" class="policy-text">${result.improved_policy.improved_policy}</pre>
//               </div>

//               ${result.improved_policy.improvements_made.length > 0 ? `
//               <div class="improvements-list">
//                   <h4><i class="fas fa-tools"></i> التحسينات المطبقة (${result.improved_policy.improvements_made.length})</h4>
//                   ${result.improved_policy.improvements_made.map((imp, idx) => `
//                       <div class="improvement-item">
//                           <div class="improvement-header">
//                               <span class="improvement-number">${idx + 1}</span>
//                               <span class="improvement-category">${imp.category}</span>
//                           </div>
//                           <div class="improvement-desc">${imp.description}</div>
//                           ${imp.before ? `
//                               <div class="before-after">
//                                   <div class="before">
//                                       <strong>قبل:</strong> "${imp.before}"
//                                   </div>
//                                   <div class="after">
//                                       <strong>بعد:</strong> "${imp.after}"
//                                   </div>
//                               </div>
//                           ` : `
//                               <div class="after-only">
//                                   <strong>تم إضافة:</strong> "${imp.after}"
//                               </div>
//                           `}
//                       </div>
//                   `).join('')}
//               </div>
//               ` : ''}

//               ${result.improved_policy.compliance_enhancements.length > 0 ? `
//               <div class="enhancements-list">
//                   <h4><i class="fas fa-check-double"></i> تحسينات الامتثال</h4>
//                   ${result.improved_policy.compliance_enhancements.map(enh => `
//                       <div class="enhancement-item">• ${enh}</div>
//                   `).join('')}
//               </div>
//               ` : ''}

//               ${result.improved_policy.key_additions.length > 0 ? `
//               <div class="additions-list">
//                   <h4><i class="fas fa-plus-circle"></i> إضافات رئيسية</h4>
//                   ${result.improved_policy.key_additions.map(add => `
//                       <div class="addition-item">✓ ${add}</div>
//                   `).join('')}
//               </div>
//               ` : ''}

//               ${result.improved_policy.notes ? `
//               <div class="notes-box">
//                   <h4><i class="fas fa-sticky-note"></i> ملاحظات</h4>
//                   <p>${result.improved_policy.notes}</p>
//               </div>
//               ` : ''}
//           </div>
//       </div>
//       ` : ''}

//       <div class="export-buttons">
//           <button class="btn" onclick="exportReport()">
//               <i class="fas fa-download"></i> تصدير التقرير (JSON)
//           </button>
//           <button class="btn" onclick="window.print()">
//               <i class="fas fa-print"></i> طباعة التقرير
//           </button>
//       </div>
//   `;

//   document.getElementById('reportContent').innerHTML = html;
//   document.getElementById('reportSection').style.display = 'block';
// }

// function exportReport() {
//   if (!currentReport) return;
  
//   const dataStr = JSON.stringify(currentReport, null, 2);
//   const dataBlob = new Blob([dataStr], {type: 'application/json'});
//   const url = URL.createObjectURL(dataBlob);
//   const link = document.createElement('a');
//   link.href = url;
//   link.download = `compliance_report_${Date.now()}.json`;
//   link.click();
// }

// function copyImprovedPolicy() {
//   const policyText = document.getElementById('improvedPolicyText').textContent;
//   navigator.clipboard.writeText(policyText).then(() => {
//       showSuccess('✅ تم نسخ السياسة المحسّنة!');
//   }).catch(err => {
//       showError('❌ فشل النسخ: ' + err);
//   });
// }