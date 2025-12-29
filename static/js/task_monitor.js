/**
 * Task Monitoring using Server-Sent Events (SSE)
 * Zero polling overhead, Real-time updates.
 */

class TaskMonitor {
  constructor(taskId, onUpdate, onComplete, onError) {
      this.taskId = taskId;
      this.onUpdate = onUpdate;
      this.onComplete = onComplete;
      this.onError = onError;
      this.eventSource = null;
  }

  start() {
      console.log(`📡 Connecting to stream for: ${this.taskId.substring(0, 30)}...`);
      
      // Open the persistent connection
      this.eventSource = new EventSource(`http://localhost:8000/api/task/${this.taskId}/stream`);

      // Handle incoming messages
      this.eventSource.onmessage = (event) => {
          try {
              const data = JSON.parse(event.data);
              this.handleUpdate(data);
          } catch (e) {
              console.error("Error parsing SSE data:", e);
          }
      };

      // Handle connection errors
      this.eventSource.onerror = (err) => {
          console.error("❌ SSE Connection Error:", err);
          this.stop();
          // Optional: Implement retry logic here if needed, 
          // but usually EventSource retries automatically.
          // If the server closes connection (finished), we treat it as done.
          if (this.eventSource.readyState === EventSource.CLOSED) {
              console.log("Stream closed normally");
          } else {
               this.onError("فقد الاتصال بالخادم. يرجى تحديث الصفحة.");
          }
      };
  }

  handleUpdate(data) {
      console.log(`📊 Stream update:`, data.status);

      if (data.status === 'completed') {
          this.onComplete(data);
          this.stop(); // Important: Close connection when done
      } 
      else if (data.status === 'failed') {
          this.onError(data.error || 'حدث خطأ غير معروف');
          this.stop();
      } 
      else if (data.status === 'processing' || data.status === 'pending') {
          // Handle pending state specifically for UI
          if (data.status === 'pending') {
              this.onUpdate({
                  current: 0, 
                  total: 100, 
                  status: 'في انتظار المعالجة... (Server Queue)'
              });
          } else {
              this.onUpdate(data.progress);
          }
      }
  }

  stop() {
      if (this.eventSource) {
          this.eventSource.close();
          this.eventSource = null;
          console.log("🛑 EventSource connection closed.");
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
                  <span id="progressStep">المرحلة 0 من 4</span>
              </div>
              <div class="progress-note" id="progressNote" style="margin-top: 10px; font-size: 12px; color: #666; text-align: center;"></div>
          </div>
      `;
  }

  update(progress) {
      const { current, total, status } = progress;
      const percentage = Math.round((current / total) * 100);

      document.getElementById('progressStatus').textContent = status || 'جاري المعالجة...';
      document.getElementById('progressPercentage').textContent = `${percentage}%`;
      document.getElementById('progressBar').style.width = `${percentage}%`;
      document.getElementById('progressStep').textContent = `المرحلة ${current} من ${total}`;
      
      // Show note if stuck on pending
      if (current === 0 && status.includes('تأكد من تشغيل')) {
          document.getElementById('progressNote').innerHTML = 
              '⚠️ يبدو أن Worker غير قيد التشغيل.<br>' +
              'يُرجى فتح terminal جديد وتشغيل:<br>' +
              '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">' +
              'celery -A celery_worker worker --loglevel=info --pool=solo' +
              '</code>';
      }
  }

  complete() {
      document.getElementById('progressStatus').textContent = '✅ اكتمل التحليل!';
      document.getElementById('progressPercentage').textContent = '100%';
      document.getElementById('progressBar').style.width = '100%';
      document.getElementById('progressBar').style.background = 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)';
      document.getElementById('progressNote').textContent = '';
  }

  error(message) {
      document.getElementById('progressStatus').innerHTML = `❌ خطأ`;
      document.getElementById('progressBar').style.background = 'linear-gradient(135deg, #c0392b 0%, #e74c3c 100%)';
      document.getElementById('progressNote').innerHTML = message.replace(/\n/g, '<br>');
      document.getElementById('progressNote').style.color = '#c0392b';
  }

  hide() {
      this.container.innerHTML = '';
  }
}

// Export for use in main app
window.TaskMonitor = TaskMonitor;
window.ProgressBar = ProgressBar;