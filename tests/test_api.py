import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    """اختبار نقطة فحص الصحة"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_get_policy_types():
    """اختبار الحصول على أنواع السياسات"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/policy-types")
    assert response.status_code == 200
    data = response.json()
    assert "policy_types" in data
    assert len(data["policy_types"]) == 3

@pytest.mark.asyncio
async def test_analyze_policy_success():
    """اختبار تحليل سياسة صحيحة"""
    test_data = {
        "shop_name": "متجر اختبار",
        "shop_specialization": "إلكترونيات",
        "policy_type": "سياسات الاسترجاع و الاستبدال",
        "policy_text": "يحق للعميل إرجاع المنتج خلال 7 أيام من تاريخ الاستلام دون إبداء أسباب. يجب أن يكون المنتج في حالته الأصلية مع الفاتورة. لا يقبل إرجاع المنتجات الإلكترونية المفتوحة."
    }
    
    async with AsyncClient(app=app, base_url="http://test", timeout=60.0) as ac:
        response = await ac.post("/api/analyze", json=test_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "compliance_report" in data or "policy_match" in data

@pytest.mark.asyncio
async def test_analyze_policy_validation_error():
    """اختبار الفشل عند بيانات غير صحيحة"""
    test_data = {
        "shop_name": "متجر اختبار",
        # missing shop_specialization
        "policy_type": "سياسات الاسترجاع و الاستبدال",
        "policy_text": "نص قصير"
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/analyze", json=test_data)
    
    assert response.status_code == 422  # Validation Error

@pytest.mark.asyncio
async def test_analyze_policy_short_text():
    """اختبار الفشل عند نص قصير جداً"""
    test_data = {
        "shop_name": "متجر اختبار",
        "shop_specialization": "إلكترونيات",
        "policy_type": "سياسات الاسترجاع و الاستبدال",
        "policy_text": "نص قصير"  # أقل من 50 حرف
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/analyze", json=test_data)
    
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_root_endpoint():
    """اختبار الصفحة الرئيسية"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

# اختبارات إضافية للنماذج
def test_policy_type_enum():
    """اختبار قيم نوع السياسة"""
    from app.models import PolicyType
    
    assert PolicyType.RETURN_EXCHANGE.value == "سياسات الاسترجاع و الاستبدال"
    assert PolicyType.PRIVACY_ACCOUNT.value == "سياسة الحساب و الخصوصية"
    assert PolicyType.SHIPPING_DELIVERY.value == "سياسة الشحن و التوصيل"

def test_compliance_report_model():
    """اختبار نموذج تقرير الامتثال"""
    from app.models import ComplianceReport, CriticalIssue
    
    report = ComplianceReport(
        overall_compliance_ratio=85.5,
        compliance_grade="جيد جداً",
        critical_issues=[
            CriticalIssue(
                phrase="عبارة مخالفة",
                severity="high",
                compliance_ratio=50.0,
                suggestion="اقتراح للتحسين",
                legal_reference="المادة 13"
            )
        ],
        strengths=[],
        weaknesses=[],
        ambiguities=[],
        summary="ملخص التقرير",
        recommendations=["توصية 1", "توصية 2"]
    )
    
    assert report.overall_compliance_ratio == 85.5
    assert report.compliance_grade == "جيد جداً"
    assert len(report.critical_issues) == 1
    assert report.critical_issues[0].phrase == "عبارة مخالفة"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])