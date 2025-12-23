import pandas as pd
import matplotlib.pyplot as plt
from app.utils.tokens_counter import TokenTracker

class TokenDashboard(TokenTracker):
    def plot_usage(self):
        """رسم بياني للاستخدام"""
        if not self.stats["requests_history"]:
            print("لا توجد بيانات للعرض")
            return
        
        df = pd.DataFrame(self.stats["requests_history"])
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        # Token usage per request
        axes[0, 0].bar(df["request_number"], df["input_tokens"], label="Input")
        axes[0, 0].bar(df["request_number"], df["output_tokens"], 
                       bottom=df["input_tokens"], label="Output")
        axes[0, 0].set_title("Tokens per Request")
        axes[0, 0].legend()
        
        # Cumulative tokens
        axes[0, 1].plot(df["request_number"], df["total_tokens"].cumsum())
        axes[0, 1].set_title("Cumulative Tokens")
        
        # Input vs Output ratio
        axes[1, 0].pie([self.stats["total_input_tokens"], 
                       self.stats["total_output_tokens"]], 
                      labels=["Input", "Output"], autopct='%1.1f%%')
        axes[1, 0].set_title("Input vs Output Distribution")
        
        # Average tokens
        avg_data = {
            "Avg Input": df["input_tokens"].mean(),
            "Avg Output": df["output_tokens"].mean(),
            "Avg Total": df["total_tokens"].mean()
        }
        axes[1, 1].bar(avg_data.keys(), avg_data.values())
        axes[1, 1].set_title("Average Tokens")
        
        plt.tight_layout()
        plt.savefig("token_usage_dashboard.png")
        print("✅ تم حفظ الـ Dashboard في: token_usage_dashboard.png")

# الاستخدام
dashboard = TokenDashboard(model="gpt-4")
# ... استخدام عادي
dashboard.plot_usage()