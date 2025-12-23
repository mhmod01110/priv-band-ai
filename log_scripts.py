#!/usr/bin/env python3
"""
مجموعة سكريبتات لإدارة وتحليل Logs
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Any

# =============================================================================
# cleanup_logs.py - تنظيف Logs القديمة
# =============================================================================

def cleanup_old_logs(days_to_keep: int = 30, dry_run: bool = False):
    """
    حذف logs أقدم من عدد معين من الأيام
    
    Args:
        days_to_keep: عدد الأيام للاحتفاظ بالـ logs
        dry_run: إذا كان True، عرض الملفات فقط بدون حذف
    """
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        print("مجلد logs غير موجود")
        return
    
    deleted_count = 0
    total_size = 0
    
    for log_type in ["prompts", "responses", "errors", "analytics"]:
        type_dir = logs_dir / log_type
        if not type_dir.exists():
            continue
        
        print(f"\n🔍 فحص {log_type}/")
        
        for log_file in type_dir.iterdir():
            if log_file.is_file():
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    file_size = log_file.stat().st_size
                    total_size += file_size
                    deleted_count += 1
                    
                    if dry_run:
                        print(f"  [سيتم حذف] {log_file.name} ({file_size / 1024:.2f} KB)")
                    else:
                        log_file.unlink()
                        print(f"  [تم حذف] {log_file.name}")
    
    print(f"\n{'سيتم' if dry_run else 'تم'} حذف {deleted_count} ملف بحجم {total_size / 1024 / 1024:.2f} MB")
    
    if dry_run:
        print("\n⚠️  هذا فحص تجريبي. لتنفيذ الحذف فعلياً، أزل المعامل dry_run")

# =============================================================================
# archive_logs.py - أرشفة Logs
# =============================================================================

def archive_logs(month: str = None):
    """
    أرشفة logs لشهر معين
    
    Args:
        month: الشهر بصيغة YYYYMM (مثال: 202412)، أو None للشهر الماضي
    """
    if month is None:
        last_month = datetime.now().replace(day=1) - timedelta(days=1)
        month = last_month.strftime('%Y%m')
    
    logs_dir = Path("logs")
    archive_dir = Path("archives")
    archive_dir.mkdir(exist_ok=True)
    
    archive_name = f"logs_archive_{month}"
    temp_dir = Path(f"temp_{archive_name}")
    temp_dir.mkdir(exist_ok=True)
    
    print(f"📦 أرشفة logs لشهر {month}")
    
    file_count = 0
    
    for log_type in ["prompts", "responses", "errors", "analytics"]:
        type_dir = logs_dir / log_type
        if not type_dir.exists():
            continue
        
        temp_type_dir = temp_dir / log_type
        temp_type_dir.mkdir(exist_ok=True)
        
        for log_file in type_dir.iterdir():
            if log_file.is_file() and month in log_file.name:
                shutil.copy2(log_file, temp_type_dir / log_file.name)
                file_count += 1
    
    if file_count == 0:
        print(f"⚠️  لم يتم العثور على ملفات لشهر {month}")
        shutil.rmtree(temp_dir)
        return
    
    # إنشاء أرشيف مضغوط
    archive_path = archive_dir / archive_name
    shutil.make_archive(str(archive_path), 'zip', temp_dir)
    shutil.rmtree(temp_dir)
    
    archive_size = (archive_path.with_suffix('.zip')).stat().st_size / 1024 / 1024
    
    print(f"✅ تم إنشاء الأرشيف: {archive_name}.zip")
    print(f"📊 عدد الملفات: {file_count}")
    print(f"💾 الحجم: {archive_size:.2f} MB")

# =============================================================================
# daily_report.py - تقرير يومي
# =============================================================================

def generate_daily_report(date_str: str = None) -> Dict[str, Any]:
    """
    إنشاء تقرير يومي شامل
    
    Args:
        date_str: التاريخ بصيغة YYYYMMDD، أو None لليوم الحالي
    
    Returns:
        قاموس يحتوي على الإحصائيات
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    analytics_file = Path(f"logs/analytics/analytics_{date_str}.jsonl")
    
    if not analytics_file.exists():
        print(f"❌ لا يوجد ملف إحصائيات لتاريخ {date_str}")
        return {}
    
    # قراءة البيانات
    analyses = []
    with open(analytics_file, 'r', encoding='utf-8') as f:
        analyses = [json.loads(line) for line in f]
    
    if not analyses:
        print("⚠️  الملف فارغ")
        return {}
    
    # حساب الإحصائيات
    total = len(analyses)
    successful = sum(1 for a in analyses if a['success'])
    failed = total - successful
    
    successful_analyses = [a for a in analyses if a['success']]
    
    if successful > 0:
        avg_compliance = sum(a['compliance_ratio'] for a in successful_analyses) / successful
        avg_duration = sum(a['duration_seconds'] for a in successful_analyses) / successful
        min_compliance = min(a['compliance_ratio'] for a in successful_analyses)
        max_compliance = max(a['compliance_ratio'] for a in successful_analyses)
    else:
        avg_compliance = 0
        avg_duration = 0
        min_compliance = 0
        max_compliance = 0
    
    # تجميع حسب نوع السياسة
    by_policy = defaultdict(lambda: {'count': 0, 'successful': 0, 'avg_compliance': 0})
    for a in analyses:
        policy = a['policy_type']
        by_policy[policy]['count'] += 1
        if a['success']:
            by_policy[policy]['successful'] += 1
            by_policy[policy]['avg_compliance'] += a['compliance_ratio']
    
    for policy in by_policy:
        if by_policy[policy]['successful'] > 0:
            by_policy[policy]['avg_compliance'] /= by_policy[policy]['successful']
    
    # تجميع حسب المتاجر
    shops = defaultdict(int)
    for a in analyses:
        shops[a['shop_name']] += 1
    top_shops = sorted(shops.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # توزيع نسب الامتثال
    compliance_ranges = {
        '90-100%': 0,
        '80-89%': 0,
        '70-79%': 0,
        '60-69%': 0,
        '50-59%': 0,
        '<50%': 0
    }
    
    for a in successful_analyses:
        ratio = a['compliance_ratio']
        if ratio >= 90:
            compliance_ranges['90-100%'] += 1
        elif ratio >= 80:
            compliance_ranges['80-89%'] += 1
        elif ratio >= 70:
            compliance_ranges['70-79%'] += 1
        elif ratio >= 60:
            compliance_ranges['60-69%'] += 1
        elif ratio >= 50:
            compliance_ranges['50-59%'] += 1
        else:
            compliance_ranges['<50%'] += 1
    
    # طباعة التقرير
    print("=" * 80)
    print(f"📊 تقرير يومي - {date_str}")
    print("=" * 80)
    print(f"\n📈 إحصائيات عامة:")
    print(f"  إجمالي التحليلات: {total}")
    print(f"  ناجح: {successful} ({successful/total*100:.1f}%)")
    print(f"  فاشل: {failed} ({failed/total*100:.1f}%)")
    
    if successful > 0:
        print(f"\n📊 نسب الامتثال:")
        print(f"  متوسط: {avg_compliance:.1f}%")
        print(f"  أدنى: {min_compliance:.1f}%")
        print(f"  أعلى: {max_compliance:.1f}%")
        print(f"  متوسط المدة: {avg_duration:.2f} ثانية")
        
        print(f"\n📉 توزيع نسب الامتثال:")
        for range_name, count in compliance_ranges.items():
            if count > 0:
                print(f"  {range_name}: {count} ({count/successful*100:.1f}%)")
    
    print(f"\n📋 تحليلات حسب نوع السياسة:")
    for policy_type, stats in by_policy.items():
        print(f"  {policy_type}:")
        print(f"    - العدد: {stats['count']}")
        print(f"    - الناجح: {stats['successful']}")
        if stats['successful'] > 0:
            print(f"    - متوسط الامتثال: {stats['avg_compliance']:.1f}%")
    
    print(f"\n🏪 أكثر المتاجر تحليلاً:")
    for shop_name, count in top_shops[:5]:
        print(f"  {shop_name}: {count} تحليل")
    
    print("=" * 80)
    
    return {
        'date': date_str,
        'total': total,
        'successful': successful,
        'failed': failed,
        'avg_compliance': avg_compliance,
        'avg_duration': avg_duration,
        'by_policy': dict(by_policy),
        'compliance_ranges': compliance_ranges,
        'top_shops': top_shops
    }

# =============================================================================
# analyze_errors.py - تحليل الأخطاء
# =============================================================================

def analyze_errors(days: int = 7):
    """
    تحليل الأخطاء في آخر عدد من الأيام
    
    Args:
        days: عدد الأيام للتحليل
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    errors_dir = Path("logs/errors")
    
    if not errors_dir.exists():
        print("❌ مجلد الأخطاء غير موجود")
        return
    
    error_files = [f for f in errors_dir.glob("error_*.json")]
    
    if not error_files:
        print("✅ لا توجد أخطاء!")
        return
    
    errors = []
    for error_file in error_files:
        file_time = datetime.fromtimestamp(error_file.stat().st_mtime)
        if file_time >= cutoff_date:
            with open(error_file, 'r', encoding='utf-8') as f:
                errors.append(json.load(f))
    
    if not errors:
        print(f"✅ لا توجد أخطاء في آخر {days} أيام!")
        return
    
    # تحليل أنواع الأخطاء
    error_types = Counter(e['error_type'] for e in errors)
    
    # تجميع حسب المتاجر
    by_shop = defaultdict(int)
    for e in errors:
        if e.get('shop_name'):
            by_shop[e['shop_name']] += 1
    
    # طباعة التحليل
    print("=" * 80)
    print(f"🔍 تحليل الأخطاء - آخر {days} أيام")
    print("=" * 80)
    print(f"\n📊 إجمالي الأخطاء: {len(errors)}")
    
    print(f"\n❌ أكثر الأخطاء شيوعاً:")
    for error_type, count in error_types.most_common(10):
        print(f"  {error_type}: {count} مرة")
    
    if by_shop:
        print(f"\n🏪 المتاجر الأكثر أخطاء:")
        for shop_name, count in sorted(by_shop.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {shop_name}: {count} خطأ")
    
    print("=" * 80)
    
    return {
        'total_errors': len(errors),
        'error_types': dict(error_types),
        'by_shop': dict(by_shop)
    }

# =============================================================================
# Main - تشغيل السكريبتات
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  python scripts.py cleanup [days] [--dry-run]")
        print("  python scripts.py archive [YYYYMM]")
        print("  python scripts.py daily-report [YYYYMMDD]")
        print("  python scripts.py analyze-errors [days]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "cleanup":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        dry_run = '--dry-run' in sys.argv
        cleanup_old_logs(days, dry_run)
    
    elif command == "archive":
        month = sys.argv[2] if len(sys.argv) > 2 else None
        archive_logs(month)
    
    elif command == "daily-report":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        generate_daily_report(date_str)
    
    elif command == "analyze-errors":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        analyze_errors(days)
    
    else:
        print(f"❌ أمر غير معروف: {command}")
        sys.exit(1)
