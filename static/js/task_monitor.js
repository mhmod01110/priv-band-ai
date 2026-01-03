/**
 * Task Monitoring with Enhanced Error Parsing
 * Handles all error types: validation, stage failures, missing data, network issues
 */

class TaskMonitor {
  constructor(taskId, onUpdate, onComplete, onError) {
      this.taskId = taskId;
      this.onUpdate = onUpdate;
      this.onComplete = onComplete;
      this.onError = onError;
      this.eventSource = null;
      this.completedStages = [];
      this.currentStage = null;
      this.lastProgress = null;
      this.pendingStartTime = null;
      this.pendingTimeout = 60000; // 60 seconds max in pending state
      this.pendingCheckInterval = null;
      this.lastStatusChange = Date.now();
      this.maxIdleTime = 120000; // 2 minutes max with no progress
  }

  getStageDisplayName(current, total) {
      const stageMap = {
          0: 'المرحلة 0: التحقق الأولي والقواعد (Validation)',
          1: 'المرحلة 1: التحقق بالذكاء الاصطناعي (AI Check)',
          2: 'المرحلة 2: البحث في الذاكرة المؤقتة (Cache)',
          3: 'المرحلة 3: تحليل الامتثال القانوني (Compliance)',
          4: 'المرحلة 4: إعادة كتابة السياسة (Regeneration)',
          5: 'المرحلة 5: إنهاء التحليل (Finalization)'
      };
      
      return stageMap[current] || `المرحلة ${current}`;
  }

  start() {
      console.log(`📡 Connecting to SSE stream for: ${this.taskId.substring(0, 30)}...`);
      
      this.eventSource = new EventSource(`http://localhost:8000/api/task/${this.taskId}/stream`);
      
      // Start timeout checker
      this.startTimeoutChecker();

      this.eventSource.onmessage = (event) => {
          try {
              const data = JSON.parse(event.data);
              this.handleUpdate(data);
          } catch (e) {
              console.error("❌ Error parsing SSE data:", e);
          }
      };

      this.eventSource.onerror = (err) => {
          console.error("❌ SSE Connection Error:", err);
          
          if (this.eventSource.readyState === EventSource.CLOSED) {
              console.log("✅ Stream closed normally");
          } else {
              this.stop();
              this.onError({
                  message: "فقد الاتصال بالخادم",
                  details: "يرجى التحقق من الاتصال بالإنترنت والمحاولة مرة أخرى.",
                  type: "network_error"
              });
          }
      };
  }
  
  startTimeoutChecker() {
      // Check every 5 seconds
      this.pendingCheckInterval = setInterval(() => {
          const now = Date.now();
          
          // Check if stuck in pending
          if (this.pendingStartTime && (now - this.pendingStartTime) > this.pendingTimeout) {
              console.error("❌ Task stuck in pending state for too long");
              this.stop();
              this.onError({
                  message: "⏱️ انتهت مهلة الانتظار",
                  details: "المهمة عالقة في قائمة الانتظار. يبدو أن Celery Worker غير قيد التشغيل أو متوقف عن العمل.",
                  type: "timeout",
                  user_action: "تأكد من تشغيل Celery Worker باستخدام: celery -A celery_worker worker --loglevel=info --pool=solo"
              });
              return;
          }
          
          // Check if no progress at all
          if ((now - this.lastStatusChange) > this.maxIdleTime) {
              console.error("❌ No progress for too long");
              this.stop();
              this.onError({
                  message: "⏱️ توقف التقدم",
                  details: "لم يتم تلقي أي تحديثات من الخادم لفترة طويلة.",
                  type: "timeout"
              });
          }
      }, 5000);
  }

  handleUpdate(data) {
      // Handle completion
      if (data.status === 'completed') {
          console.log("✅ Task completed successfully");
          this.lastStatusChange = Date.now();
          
          // Check if result contains validation error
          if (data.result && data.result.result && data.result.result.error_type === 'validation_error') {
              console.log("🚫 Validation error in completed task");
              this.onError(this.parseValidationError(data.result.result));
              this.stop();
              return;
          }

          const finalStageNum = this.lastProgress?.total || 5;
          const finalProgress = {
              current: finalStageNum,
              total: finalStageNum,
              status: '✅ انتهت العملية',
              stageDetails: this.completedStages,
              isComplete: true
          };
          
          this.onUpdate(finalProgress);
          this.onComplete(data);
          this.stop();
          return;
      }
      
      // Handle failure
      if (data.status === 'failed') {
          console.error("❌ Task failed raw:", data.error);
          this.lastStatusChange = Date.now();
          const errorDetails = this.parseErrorDetails(data.error);
          this.onError(errorDetails);
          this.stop();
          return;
      }
      
      // Handle pending
      if (data.status === 'pending') {
          // Track when pending state started
          if (!this.pendingStartTime) {
              this.pendingStartTime = Date.now();
              console.log("⏳ Task entered pending state, starting timeout monitoring");
          }
          
          const pendingDuration = Math.floor((Date.now() - this.pendingStartTime) / 1000);
          
          this.onUpdate({
              current: 0,
              total: 5,
              status: `⏳ في انتظار المعالجة... (${pendingDuration}s)`,
              stageDetails: [],
              message: 'تم إرسال الطلب بنجاح. في انتظار بدء المعالجة.'
          });
          return;
      }
      
      // Handle processing
      if (data.status === 'processing' && data.progress) {
          // Reset pending timer since we're now processing
          this.pendingStartTime = null;
          this.lastStatusChange = Date.now();
          
          const progress = data.progress;
          
          // Track stage completion
          if (this.lastProgress && progress.current > this.lastProgress.current) {
              const finishedStage = this.lastProgress.current;
              if (!this.completedStages.find(s => s.stage === finishedStage)) {
                  this.completedStages.push({
                      stage: finishedStage,
                      name: this.getStageDisplayName(finishedStage, progress.total),
                      status: '✅ مكتمل',
                      timestamp: new Date().toLocaleTimeString('ar-SA')
                  });
              }
          }
          
          this.currentStage = progress.current;
          this.lastProgress = progress;
          
          const enhancedProgress = {
              current: progress.current,
              total: progress.total,
              status: progress.status || this.getStageDisplayName(progress.current, progress.total),
              stageDetails: this.completedStages,
              currentStageName: this.getStageDisplayName(progress.current, progress.total),
              shop_name: progress.shop_name
          };
          
          this.onUpdate(enhancedProgress);
      }
  }

  /**
   * Parse validation errors (pre-stage errors)
   */
  parseValidationError(error) {
      return {
          message: error.message || 'خطأ في التحقق من البيانات',
          details: error.details || null,
          type: 'validation_error',
          error_category: error.error_category || 'unknown',
          user_action: error.user_action || null,
          stage: 'pre_validation',
          completedStages: [],
          rawError: JSON.stringify(error)
      };
  }

  /**
   * Parse stage execution errors
   */
  parseErrorDetails(error) {
      let errorStr = '';
      let errorObj = {};

      // Normalize to string
      if (typeof error === 'string') {
          errorStr = error;
      } else if (typeof error === 'object') {
          errorStr = JSON.stringify(error);
          errorObj = error;
      }

      const errorLower = errorStr.toLowerCase();
      let userMessage = errorStr;
      let technicalDetails = null;
      let errorType = 'unknown';
      let failedStage = this.currentStage || 'غير محدد';

      // Error Classification Strategy

      // 1. Validation errors (should be rare here, but handle anyway)
      if (errorObj.error_type === 'validation_error' || errorLower.includes('validation')) {
          return this.parseValidationError(errorObj);
      }

      // 2. Quota / Rate Limits
      if (errorLower.includes('quota') || errorLower.includes('429') || 
          errorLower.includes('rate limit') || errorLower.includes('insufficient_quota')) {
          errorType = 'quota_exceeded';
          userMessage = '⚠️ تم تجاوز الحد المسموح من الطلبات';
          technicalDetails = 'تم استنفاد حصة التوكنز لدى مزود الذكاء الاصطناعي. يرجى المحاولة لاحقاً.';
      }
      // 3. Timeouts
      else if (errorLower.includes('timeout') || errorLower.includes('timed out') || 
               errorLower.includes('deadline')) {
          errorType = 'timeout';
          userMessage = '⏱️ انتهت مهلة الانتظار';
          technicalDetails = 'استغرق التحليل وقتاً أطول من المتوقع. الخادم مشغول جداً حالياً.';
      }
      // 4. Authentication
      else if (errorLower.includes('401') || errorLower.includes('403') || 
               errorLower.includes('auth') || errorLower.includes('api key')) {
          errorType = 'authentication';
          userMessage = '🔐 خطأ في المصادقة';
          technicalDetails = 'هناك مشكلة في مفاتيح الربط مع مزود الخدمة.';
      }
      // 5. Server Errors
      else if (errorLower.includes('500') || errorLower.includes('502') || 
               errorLower.includes('bad gateway')) {
          errorType = 'server_error';
          userMessage = '🔥 خطأ في الخادم';
          technicalDetails = 'حدث خطأ داخلي في الخادم. يرجى المحاولة مرة أخرى.';
      }
      // 6. Network / Connection
      else if (errorLower.includes('network') || errorLower.includes('connection') || 
               errorLower.includes('fetch')) {
          errorType = 'network';
          userMessage = '🌐 خطأ في الاتصال';
          technicalDetails = 'فشل الاتصال بالخادم. تأكد من اتصالك بالإنترنت.';
      }
      // 7. Missing compliance report
      else if (errorLower.includes('compliance') || errorLower.includes('مفقودة') || 
               errorLower.includes('missing')) {
          errorType = 'missing_data';
          userMessage = '📊 بيانات التقرير مفقودة';
          technicalDetails = 'فشل إنشاء تقرير الامتثال. قد يكون هناك خطأ في المعالجة.';
      }
      // 8. Stage-specific failures
      else if (errorLower.includes('stage') || errorLower.includes('مرحلة')) {
          const stageMatch = errorStr.match(/stage[_\s]?(\d)/i) || errorStr.match(/مرحلة[_\s]?(\d)/i);
          if (stageMatch) {
              failedStage = parseInt(stageMatch[1]);
              userMessage = `❌ فشل في ${this.getStageDisplayName(failedStage, 5)}`;
              technicalDetails = errorStr;
          }
      }

      // Cleanup long messages
      if (userMessage.length > 150 && !technicalDetails) {
          technicalDetails = userMessage;
          userMessage = "حدث خطأ أثناء المعالجة";
      }

      return {
          message: userMessage,
          type: errorType,
          details: technicalDetails,
          failedStage: failedStage,
          completedStages: this.completedStages,
          rawError: errorStr
      };
  }

  stop() {
      if (this.eventSource) {
          this.eventSource.close();
          this.eventSource = null;
          console.log("🛑 EventSource connection closed");
      }
      
      if (this.pendingCheckInterval) {
          clearInterval(this.pendingCheckInterval);
          this.pendingCheckInterval = null;
          console.log("🛑 Timeout checker stopped");
      }
  }
}

/**
* Progress Bar UI Helper
*/
class ProgressBar {
  constructor(containerId) {
      this.container = document.getElementById(containerId);
      this.render();
  }

  render() {
      this.container.innerHTML = `
          <div class="progress-container">
              <div class="progress-header">
                  <span class="progress-status" id="progressStatus">جاري التحليل...</span>
                  <span class="progress-percentage" id="progressPercentage">0%</span>
              </div>
              <div class="progress-bar-container">
                  <div class="progress-bar" id="progressBar" style="width: 0%"></div>
              </div>
              <div class="progress-details" id="progressDetails">
                  <span id="progressStep">التهيئة...</span>
              </div>
              <div class="progress-note" id="progressNote" style="margin-top: 10px; font-size: 12px; color: #666; text-align: center;"></div>
          </div>
      `;
  }

  update(progress) {
      const total = progress.total || 1;
      const current = progress.current || 0;
      const percentage = Math.round((current / total) * 100);

      const statusEl = document.getElementById('progressStatus');
      const percentageEl = document.getElementById('progressPercentage');
      const barEl = document.getElementById('progressBar');
      const stepEl = document.getElementById('progressStep');
      const noteEl = document.getElementById('progressNote');

      if (statusEl) statusEl.textContent = progress.status || 'جاري المعالجة...';
      if (percentageEl) percentageEl.textContent = `${percentage}%`;
      if (barEl) barEl.style.width = `${percentage}%`;
      if (stepEl) stepEl.textContent = `المرحلة ${current} من ${total}`;
      
      if (current === 0 && barEl) {
          barEl.style.background = '#3498db';
      }
      
      // Warning about Worker
      if (current === 0 && progress.status && progress.status.includes('تأكد من تشغيل') && noteEl) {
          noteEl.innerHTML = 
              '⚠️ يبدو أن Worker غير قيد التشغيل.<br>' +
              '<code>celery -A celery_worker worker --loglevel=info --pool=solo</code>';
      } else if (noteEl) {
          noteEl.textContent = '';
      }
  }

  complete() {
      const statusEl = document.getElementById('progressStatus');
      const percentageEl = document.getElementById('progressPercentage');
      const barEl = document.getElementById('progressBar');
      const noteEl = document.getElementById('progressNote');

      if (statusEl) statusEl.textContent = '✅ اكتملت العملية!';
      if (percentageEl) percentageEl.textContent = '100%';
      if (barEl) {
          barEl.style.width = '100%';
          barEl.style.background = 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)';
      }
      if (noteEl) noteEl.textContent = '';
  }

  error(input) {
      let message = "حدث خطأ غير معروف";
      
      // Safely extract message
      if (typeof input === 'string') {
          message = input;
      } else if (input && typeof input === 'object') {
          message = input.message || JSON.stringify(input);
      }

      const statusEl = document.getElementById('progressStatus');
      const barEl = document.getElementById('progressBar');
      const noteEl = document.getElementById('progressNote');

      if (statusEl) statusEl.innerHTML = `❌ توقف`;
      if (barEl) barEl.style.background = 'linear-gradient(135deg, #c0392b 0%, #e74c3c 100%)';
      
      if (noteEl) {
          noteEl.innerHTML = message.replace(/\n/g, '<br>');
          noteEl.style.color = '#c0392b';
          noteEl.style.fontWeight = 'bold';
      }
  }

  hide() {
      this.container.innerHTML = '';
  }
}

// Export to global scope
window.TaskMonitor = TaskMonitor;
window.ProgressBar = ProgressBar;