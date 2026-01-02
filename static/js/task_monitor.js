/**
 * Task Monitoring using Server-Sent Events (SSE)
 * Zero polling overhead, Real-time updates with stage-by-stage tracking.
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
  }

  // Stage name mapping matching the Python Stage Classes
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
      
      // Open the persistent connection
      this.eventSource = new EventSource(`http://localhost:8000/api/task/${this.taskId}/stream`);

      // Handle incoming messages
      this.eventSource.onmessage = (event) => {
          try {
              const data = JSON.parse(event.data);
              this.handleUpdate(data);
          } catch (e) {
              console.error("❌ Error parsing SSE data:", e);
              // Don't kill the stream immediately on one parse error, but warn
          }
      };

      // Handle connection errors
      this.eventSource.onerror = (err) => {
          console.error("❌ SSE Connection Error:", err);
          
          if (this.eventSource.readyState === EventSource.CLOSED) {
              console.log("✅ Stream closed normally");
          } else {
              this.stop();
              // Pass a generic object, not just a string
              this.onError({
                  message: "فقد الاتصال بالخادم",
                  details: "يرجى التحقق من الاتصال بالإنترنت والمحاولة مرة أخرى.",
                  type: "network_error"
              });
          }
      };
  }

  handleUpdate(data) {
      // Handle completion
      if (data.status === 'completed') {
          console.log("✅ Task completed successfully");
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
          const errorDetails = this.parseErrorDetails(data.error);
          this.onError(errorDetails);
          this.stop();
          return;
      } 
      
      // Handle pending state
      if (data.status === 'pending') {
          this.onUpdate({
              current: 0,
              total: 5,
              status: '⏳ في انتظار المعالجة...',
              stageDetails: [],
              message: 'تم إرسال الطلب بنجاح. في انتظار بدء المعالجة.'
          });
          return;
      }
      
      // Handle processing
      if (data.status === 'processing' && data.progress) {
          const progress = data.progress;
          
          // Track stage completion
          if (this.lastProgress && progress.current > this.lastProgress.current) {
              const finishedStage = this.lastProgress.current;
              // Avoid duplicates
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
   * Robust Error Parsing Logic
   * handles strings, JSON objects, and Python-like string representations
   */
  parseErrorDetails(error) {
      let errorStr = '';
      let errorObj = {};

      // 1. Normalize input to string for regex matching
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

      // --- Error Classification Strategy ---

      // 1. Quota / Rate Limits (429)
      if (errorLower.includes('quota') || errorLower.includes('429') || errorLower.includes('rate limit') || errorLower.includes('insufficient_quota')) {
          errorType = 'quota_exceeded';
          userMessage = '⚠️ تم تجاوز الحد المسموح من الطلبات';
          technicalDetails = 'تم استنفاد حصة التوكنز لدى مزود الذكاء الاصطناعي (OpenAI/Gemini). يرجى المحاولة لاحقاً.';
      }
      // 2. Timeouts
      else if (errorLower.includes('timeout') || errorLower.includes('timed out') || errorLower.includes('deadline')) {
          errorType = 'timeout';
          userMessage = '⏱️ انتهت مهلة الانتظار';
          technicalDetails = 'استغرق التحليل وقتاً أطول من المتوقع. الخادم مشغول جداً حالياً.';
      }
      // 3. Authentication / API Keys
      else if (errorLower.includes('401') || errorLower.includes('403') || errorLower.includes('auth') || errorLower.includes('api key')) {
          errorType = 'authentication';
          userMessage = '🔐 خطأ في المصادقة';
          technicalDetails = 'هناك مشكلة في مفاتيح الربط مع مزود الخدمة.';
      }
      // 4. Server Errors (500s)
      else if (errorLower.includes('500') || errorLower.includes('502') || errorLower.includes('bad gateway')) {
          errorType = 'server_error';
          userMessage = '🔥 خطأ في الخادم';
          technicalDetails = 'حدث خطأ داخلي في الخادم. يرجى المحاولة مرة أخرى.';
      }
      // 5. Network / Connection
      else if (errorLower.includes('network') || errorLower.includes('connection') || errorLower.includes('fetch')) {
          errorType = 'network';
          userMessage = '🌐 خطأ في الاتصال';
          technicalDetails = 'فشل الاتصال بالخادم. تأكد من اتصالك بالإنترنت.';
      }
      // 6. Stage Failures
      else if (errorLower.includes('stage')) {
          const stageMatch = errorStr.match(/stage[_\s]?(\d)/i);
          if (stageMatch) {
              failedStage = parseInt(stageMatch[1]);
              userMessage = `❌ فشل في ${this.getStageDisplayName(failedStage, 5)}`;
          }
      }

      // Cleanup extremely long raw error messages for display
      if (userMessage.length > 100 && !technicalDetails) {
          technicalDetails = userMessage; // Move long text to details
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
  }
}

// Progress UI Helper
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

      document.getElementById('progressStatus').textContent = progress.status || 'جاري المعالجة...';
      document.getElementById('progressPercentage').textContent = `${percentage}%`;
      document.getElementById('progressBar').style.width = `${percentage}%`;
      document.getElementById('progressStep').textContent = `المرحلة ${current} من ${total}`;
      
      if (current === 0) {
          document.getElementById('progressBar').style.background = '#3498db';
      }
      
      // Warning about Worker
      if (current === 0 && progress.status && progress.status.includes('تأكد من تشغيل')) {
          document.getElementById('progressNote').innerHTML = 
              '⚠️ يبدو أن Worker غير قيد التشغيل.<br>' +
              '<code>celery -A celery_worker worker --loglevel=info --pool=solo</code>';
      }
  }

  complete() {
      document.getElementById('progressStatus').textContent = '✅ اكتملت العملية!';
      document.getElementById('progressPercentage').textContent = '100%';
      document.getElementById('progressBar').style.width = '100%';
      document.getElementById('progressBar').style.background = 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)';
      document.getElementById('progressNote').textContent = '';
  }

  // UPDATED: Robust error handling method
  error(input) {
      let message = "حدث خطأ غير معروف";
      
      // Safely extract message regardless of input type
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
          // Safe HTML injection
          noteEl.innerHTML = message.replace(/\n/g, '<br>');
          noteEl.style.color = '#c0392b';
          noteEl.style.fontWeight = 'bold';
      }
  }

  hide() {
      this.container.innerHTML = '';
  }
}

window.TaskMonitor = TaskMonitor;
window.ProgressBar = ProgressBar;