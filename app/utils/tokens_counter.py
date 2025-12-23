import tiktoken
from openai import OpenAI
from typing import Dict, List
import json

class TokenTracker:
    def __init__(self, model="gpt-4"):
        self.model = model
        self.client = OpenAI()
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # إحصائيات
        self.stats = {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "requests_history": []
        }
    
    def count_tokens(self, text: str) -> int:
        """حساب tokens لنص واحد"""
        return len(self.encoding.encode(text))
    
    def count_message_tokens(self, messages: List[Dict]) -> int:
        """حساب tokens لمجموعة messages"""
        tokens_per_message = 3
        tokens_per_name = 1
        
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(self.encoding.encode(str(value)))
                if key == "name":
                    num_tokens += tokens_per_name
        
        num_tokens += 3
        return num_tokens
    
    def chat_completion(self, messages: List[Dict], **kwargs) -> Dict:
        """
        استدعاء API مع تتبع الـ tokens
        """
        # حساب input tokens
        input_tokens = self.count_message_tokens(messages)
        
        # استدعاء API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        
        # الحصول على usage من الـ response
        usage = response.usage
        output_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
        
        # تحديث الإحصائيات
        request_info = {
            "request_number": self.stats["total_requests"] + 1,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "prompt_preview": messages[-1]["content"][:100] + "...",
        }
        
        self.stats["total_requests"] += 1
        self.stats["total_input_tokens"] += input_tokens
        self.stats["total_output_tokens"] += output_tokens
        self.stats["total_tokens"] += total_tokens
        self.stats["requests_history"].append(request_info)
        
        # طباعة معلومات الـ request
        self.print_request_info(request_info)
        
        return response
    
    def print_request_info(self, info: Dict):
        """طباعة معلومات الـ request"""
        print("\n" + "="*60)
        print(f"📊 Request #{info['request_number']}")
        print("-"*60)
        print(f"📥 Input Tokens:  {info['input_tokens']:,}")
        print(f"📤 Output Tokens: {info['output_tokens']:,}")
        print(f"📦 Total Tokens:  {info['total_tokens']:,}")
        print("="*60 + "\n")
    
    def print_summary(self):
        """طباعة ملخص الاستخدام الكلي"""
        print("\n" + "="*60)
        print("📈 إجمالي الاستخدام")
        print("="*60)
        print(f"🔢 عدد الـ Requests:        {self.stats['total_requests']}")
        print(f"📥 إجمالي Input Tokens:   {self.stats['total_input_tokens']:,}")
        print(f"📤 إجمالي Output Tokens:  {self.stats['total_output_tokens']:,}")
        print(f"📦 إجمالي Total Tokens:   {self.stats['total_tokens']:,}")
        print("="*60)
        
        # حساب التكلفة التقريبية (GPT-4)
        # $0.03 per 1K input tokens, $0.06 per 1K output tokens
        input_cost = (self.stats['total_input_tokens'] / 1000) * 0.03
        output_cost = (self.stats['total_output_tokens'] / 1000) * 0.06
        total_cost = input_cost + output_cost
        
        print(f"\n💰 التكلفة التقريبية:")
        print(f"   Input:  ${input_cost:.4f}")
        print(f"   Output: ${output_cost:.4f}")
        print(f"   Total:  ${total_cost:.4f}")
        print("="*60 + "\n")
    
    def export_stats(self, filename="token_stats.json"):
        """تصدير الإحصائيات لملف JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        print(f"✅ تم حفظ الإحصائيات في: {filename}")

# مثال الاستخدام
tracker = TokenTracker(model="gpt-4")

messages = [
    {"role": "system", "content": "أنت محلل قانوني متخصص"},
    {"role": "user", "content": "قم بتحليل السياسة التالية..."}
]

# استدعاء API
response = tracker.chat_completion(
    messages=messages,
    temperature=0.3,
    max_tokens=2000
)

# استخدام النتيجة
result = response.choices[0].message.content
print(result)

# طباعة الملخص
tracker.print_summary()

# حفظ الإحصائيات
tracker.export_stats()