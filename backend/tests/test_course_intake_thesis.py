"""Unified intake, Course Thesis, and canonical family adapter contracts."""

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from app.ai.provider import CourseBrief
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.generation.domain_adapters import ADAPTER_IDS, build_course_quality_contract
from app.models.enums import CourseFamily, ExplanationLevel, StructureMode


def _brief(**changes) -> CourseBrief:
    values = {
        "title": "تحليل عمليات المتجر",
        "audience": "صاحب متجر لديه خبرة ميدانية",
        "outcome": "تحسين قرار إعادة الطلب",
        "structure_mode": StructureMode.CONNECTED_NO_MODULES,
        "explanation_level": ExplanationLevel.FINAL_ONLY,
    }
    values.update(changes)
    return CourseBrief(**values)


def test_all_canonical_course_families_have_distinct_real_adapters():
    expected = {family.value for family in CourseFamily}
    assert set(ADAPTER_IDS) == expected

    signatures = {}
    for family in CourseFamily:
        contract = build_course_quality_contract(
            _brief(primary_course_family=family)
        )
        assert contract.adapter_id == family.value
        signatures[family] = (
            tuple(contract.pedagogy.practice_types),
            tuple(contract.pedagogy.assessment_types),
            tuple(contract.pedagogy.project_types),
            tuple(contract.pedagogy.domain_specific_validators),
        )
    assert len(set(signatures.values())) == len(CourseFamily)


def test_thesis_copies_full_intake_without_inventing_instructor_experience():
    brief = _brief(
        course_type="practical_skill",
        course_domain="retail_operations",
        course_specialty="inventory",
        primary_course_family=CourseFamily.ANALYTICAL_OPERATIONAL,
        secondary_course_families=[CourseFamily.SALES_MARKETING_BUSINESS],
        student_language="ar",
        spoken_variety="egyptian_colloquial",
        learner_starting_state="يدير المخزون يدويا ولم يستخدم نموذج طلب",
        required_final_performance="يبني قرار طلب أسبوعي قابل للتدقيق",
        required_independence_level="independent",
        instructor_responsibility_boundaries=["لا يقدم اعتمادا محاسبيا"],
        forbidden_first_person_claims=["أنا أدرت مئات المتاجر"],
        realistic_student_budget="أدوات مجانية أو منخفضة التكلفة",
        available_tools=["Excel"],
        professional_constraints=["فرّق بين المثال والسياسة الفعلية"],
    )

    thesis = build_course_thesis_from_brief(brief)

    assert thesis.course_domain == "retail_operations"
    assert thesis.course_specialty == "inventory"
    assert thesis.primary_course_family is CourseFamily.ANALYTICAL_OPERATIONAL
    assert thesis.learner_starting_state == brief.learner_starting_state
    assert thesis.required_final_performance == brief.required_final_performance
    assert thesis.required_independence_level == "independent"
    assert thesis.required_tools == ["Excel"]
    assert thesis.verified_instructor_experience == []
    assert thesis.forbidden_first_person_claims == ["أنا أدرت مئات المتاجر"]
    assert thesis.beginner_assumption_policy == "no_undeclared_prerequisites"
    assert thesis.experienced_learner_policy == "respect_existing_competence"


def test_only_explicit_verified_experience_enters_contract():
    inferred = build_course_quality_contract(
        _brief(
            title="خبرة الاستشاري المحترف",
            primary_course_family=CourseFamily.PROFESSIONAL_SERVICE,
        )
    )
    explicit = build_course_quality_contract(
        _brief(
            primary_course_family=CourseFamily.PROFESSIONAL_SERVICE,
            verified_instructor_experience=["نفّذ المشروع الموثق س"],
        )
    )
    assert inferred.evidence.verified_instructor_experience == []
    assert explicit.evidence.verified_instructor_experience == [
        "نفّذ المشروع الموثق س"
    ]


def test_high_stakes_family_is_fail_closed_for_export_review():
    contract = build_course_quality_contract(
        _brief(
            primary_course_family=CourseFamily.HIGH_STAKES_AUTHORITY_SENSITIVE,
            high_stakes_constraints=["لا تشخّص حالة فردية"],
        )
    )
    assert contract.evidence.risk_level == "critical"
    assert contract.evidence.claim_verification_policy == "expert_gate"
    assert contract.evidence.require_expert_review_before_export is True
    assert contract.evidence.high_stakes_constraints == ["لا تشخّص حالة فردية"]


def test_course_api_persists_and_returns_unified_intake(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'intake.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    from app.main import app

    payload = {
        "title": "تحليل المخزون",
        "audience": "مبتدئ بلا خلفية تحليلية",
        "outcome": "يبني قرار إعادة طلب",
        "structure_mode": "connected_no_modules",
        "course_domain": "retail",
        "course_specialty": "inventory",
        "primary_course_family": "analytical_operational",
        "secondary_course_families": ["sales_marketing_business"],
        "target_market": "egypt",
        "student_language": "ar",
        "spoken_variety": "egyptian_colloquial",
        "address_form": "neutral",
        "learner_starting_state": "مبتدئ بلا خلفية تحليلية",
        "required_final_performance": "يبني قرارا أسبوعيا قابلا للتدقيق",
        "required_independence_level": "independent_with_checklist",
        "instructor_responsibility_boundaries": ["لا يقدم اعتمادا محاسبيا"],
        "verified_instructor_experience": [],
        "forbidden_first_person_claims": ["أنا ضمنت أرباحا"],
        "realistic_student_budget": "مجاني إلى 500 جنيه شهريا",
        "available_tools": ["Excel", "Google Sheets"],
        "professional_constraints": ["الأرقام أمثلة وليست ضمانات"],
        "high_stakes_constraints": [],
    }
    with TestClient(app) as client:
        response = client.post("/courses", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["primary_course_family"] == "analytical_operational"
        assert body["secondary_course_families"] == ["sales_marketing_business"]
        assert body["address_form"] == "neutral"
        assert body["available_tools"] == ["Excel", "Google Sheets"]
        assert body["verified_instructor_experience"] == []

        updated = client.put(
            f"/courses/{body['id']}",
            json={
                "primary_course_family": "programming_technical",
                "secondary_course_families": ["programming_technical"],
                "verified_instructor_experience": ["خبرة موثقة أدخلها المستخدم"],
            },
        )
        assert updated.status_code == 200, updated.text
        changed = updated.json()
        assert changed["primary_course_family"] == "programming_technical"
        assert changed["secondary_course_families"] == []
        assert changed["verified_instructor_experience"] == [
            "خبرة موثقة أدخلها المستخدم"
        ]
