from __future__ import annotations

from app.generation.export_blockers import evaluate_export_blockers
from app.generation.quality.cross_scope_review import review_cross_scope
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    LessonSemanticContract,
    ModulePlan,
    ModuleProject,
    ReelPlan,
    ReviewStatus,
)


def _contract(topic: str, capability: str) -> LessonSemanticContract:
    return LessonSemanticContract(
        learner_before=f"المتعلم لا يحسم {topic} بوضوح",
        learner_after=f"المتعلم ينفذ {capability} باستقلال",
        exact_capability_change=capability,
        strongest_non_obvious_meaning=f"أثر {topic} يظهر في القرار لا الزينة",
        misconception_or_failure=f"تطبيق {topic} بلا شرط يفسد النتيجة",
        causal_explanation=f"يتغير الناتج لأن {topic} يتحكم في المسار",
        proof_example_or_demonstration=f"قارن حالتين تختلفان في {topic} فقط",
        learner_test_or_action=f"نفذ {topic} على حالة جديدة وافحص الفرق",
        boundary_or_exception=f"لا تعمم {topic} خارج شرط الحالة",
        real_tension=f"وازن بين وضوح {topic} وعدم المبالغة",
        complete_payoff=f"يكتمل تطبيق {topic} بنتيجة قابلة للمراجعة",
        earned_next_need=f"بعد {topic} يصبح الناتج مدخلا للقرار التالي",
        escalation_role=f"يرفع {topic} استقلال المتعلم في التنفيذ",
        sequence_dependency=f"يعتمد {topic} على نتيجة الخطوة السابقة",
    )


def _plan(reel_id: str, topic: str, capability: str) -> ReelPlan:
    return ReelPlan(
        reel_id=reel_id,
        title=topic,
        purpose=capability,
        must_cover=[topic, capability],
        new_skill_or_decision=capability,
        distinct_teaching_outcome=capability,
        student_can_do_after=capability,
        lesson_semantic_contract=_contract(topic, capability),
    )


def _generated(
    plan: ReelPlan,
    module_id: str,
    *,
    opening: str,
    ending: str,
    middle: str,
    used_ideas: bool = True,
) -> GeneratedReel:
    return GeneratedReel(
        reel_id=plan.reel_id,
        module_id=module_id,
        title=plan.title,
        script_text=f"{opening}\n{middle}\n{ending}",
        spoken_beats=[opening, middle, ending],
        used_ideas=[plan.new_skill_or_decision] if used_ideas else [],
        used_examples=[f"مثال {plan.reel_id}"],
        self_check_status=ReviewStatus.PASS,
        quality_status="pass",
    )


def _healthy_case() -> tuple[CourseMap, list[GeneratedReel]]:
    specs = [
        ("m1-r1", "ترتيب الألوان", "يفرز الألوان حسب وظيفة الرسالة"),
        ("m1-r2", "مساحة العنوان", "يضبط المسافة حول العنوان المقروء"),
        ("m2-r1", "اختبار الهاتف", "يفحص التصميم على شاشة هاتف حقيقية"),
        ("m2-r2", "تسليم الملف", "يصدر ملفا يحافظ على جودة العرض"),
    ]
    plans = [_plan(*spec) for spec in specs]
    module_one = ModulePlan(
        module_id="m1",
        title="قرارات الترتيب",
        purpose="ترتيب الرسالة بصريا",
        reels=plans[:2],
        module_project=ModuleProject(
            name="لوحة مرتبة",
            brief="نفذ لوحة واضحة",
            skills_tested=["يفرز الألوان", "يضبط المسافة"],
        ),
    )
    module_two = ModulePlan(
        module_id="m2",
        title="الفحص والتسليم",
        purpose="فحص الناتج وتسليمه",
        reels=plans[2:],
        module_project=ModuleProject(
            name="ملف جاهز",
            brief="افحص ثم صدر الملف",
            skills_tested=["يفحص التصميم", "يصدر ملفا"],
        ),
    )
    course_map = CourseMap(
        course_title="تصميم واضح",
        main_thread="من ترتيب الرسالة إلى تسليمها",
        modules=[module_one, module_two],
        graduation_project=ModuleProject(
            name="مشروع نهائي",
            brief="سلم تصميما كاملا",
            skills_tested=["يفرز الألوان", "يصدر ملفا"],
        ),
    )
    generated = [
        _generated(
            plans[0],
            "m1",
            opening="ابدأ بملاحظة أين تقع عينك أول مرة",
            middle="فرز اللون يوضح وظيفة الرسالة ويعطيك اختبارا عمليا واضحا",
            ending="اللوحة الآن تملك ترتيب لون يمكن قياسه",
        ),
        _generated(
            plans[1],
            "m1",
            opening="المسافة الضيقة تخنق العنوان حتى لو كان الخط سليما",
            middle="اضبط الفراغ ثم قارن القراءة على حجمين مختلفين قبل الاعتماد",
            ending="صار العنوان مقروءا وبقي أن نفحصه على الهاتف",
        ),
        _generated(
            plans[2],
            "m2",
            opening="شاشة المكتب لا تكشف كل مشكلة تظهر على الهاتف",
            middle="افتح النسخة الحقيقية واختبر الحجم والتباين بيد واحدة",
            ending="نجح فحص الهاتف وأصبح الملف مستعدا للتصدير",
        ),
        _generated(
            plans[3],
            "m2",
            opening="اختيار صيغة التسليم قرار جودة وليس خطوة حفظ فقط",
            middle="صدّر نسخة تجريبية وافحص الحواف والوضوح قبل الملف النهائي",
            ending="الملف النهائي يحافظ على جودة العرض ويمكن تسليمه بثقة",
        ),
    ]
    return course_map, generated


def _final_course(course_map: CourseMap, reels: list[GeneratedReel]) -> FinalCourse:
    by_module = {
        module.module_id: [reel for reel in reels if reel.module_id == module.module_id]
        for module in course_map.modules
    }
    modules = [
        FinalModule(
            module_id=module.module_id,
            title=module.title,
            module_project=module.module_project,
            reels=[
                FinalReel(
                    reel_id=reel.reel_id,
                    title=reel.title,
                    script_text=reel.script_text,
                    quality_status=reel.quality_status,
                )
                for reel in by_module[module.module_id]
            ],
        )
        for module in course_map.modules
    ]
    return FinalCourse(
        title=course_map.course_title,
        full_text="\n".join(reel.script_text for reel in reels),
        modules=modules,
        graduation_project=course_map.graduation_project,
    )


def test_healthy_course_passes_all_four_review_scopes() -> None:
    course_map, reels = _healthy_case()
    report = review_cross_scope(course_map=course_map, generated_reels=reels)
    assert report.ok, report.model_dump()


def test_cross_scope_findings_cover_required_failure_classes() -> None:
    course_map, reels = _healthy_case()
    modules = list(course_map.modules)
    second_reels = list(modules[1].reels)
    second_reels[0] = second_reels[0].model_copy(
        update={
            "lesson_semantic_contract": second_reels[0].lesson_semantic_contract.model_copy(
                update={
                    "exact_capability_change": modules[0].reels[-1]
                    .lesson_semantic_contract.exact_capability_change
                }
            ),
            "prerequisite_lesson_ids": ["missing-prerequisite"],
        }
    )
    modules[1] = modules[1].model_copy(
        update={
            "reels": second_reels,
            "module_project": modules[1].module_project.model_copy(
                update={"skills_tested": ["يحسب ضريبة الرواتب"]}
            ),
        }
    )
    broken_map = course_map.model_copy(update={"modules": modules})
    repeated_opening = "دايما استخدم ثلاث نقاط قياس قبل قرار التسليم"
    repeated_ending = "نفس الخلاصة الجاهزة تتكرر في نهاية كل تطبيق"
    reels[0] = reels[0].model_copy(
        update={
            "script_text": (
                "ابدأ بتحليل الحالة وتحديد الرسالة والجمهور والشرط العملي قبل القرار\n"
                "قارن أربع حالات مختلفة وسجل سبب كل اختيار ثم اختبر النتيجة "
                "على شاشة صغيرة وشاشة كبيرة ومع مستخدم جديد قبل اعتماد التطبيق\n"
                "اختم بإثبات واضح يربط السبب بالمثال وبالفعل الذي سينفذه المتعلم"
            )
        }
    )
    reels[1] = reels[1].model_copy(
        update={
            "script_text": (
                f"{repeated_opening}\n"
                "اشرح القياس بسبب واضح ومثال قابل للفحص\n"
                f"{repeated_ending}"
            )
        }
    )
    reels[2] = reels[2].model_copy(
        update={
            "script_text": (
                f"{repeated_opening}\n"
                "قارن الناتج ثم طبق القرار على حالة أخرى\n"
                f"{repeated_ending}"
            )
        }
    )
    reels[-1] = reels[-1].model_copy(
        update={
            "script_text": (
                "ممنوع استخدم ثلاث نقاط قياس قبل قرار التسليم\n"
                "مفهوم مهم\nطبق المهارة"
            ),
            "used_ideas": [],
        }
    )

    report = review_cross_scope(course_map=broken_map, generated_reels=reels)
    codes = {finding.code for finding in report.blocking_findings}
    scopes = {finding.scope for finding in report.blocking_findings}

    assert not report.ok
    assert {"lesson", "module", "adjacent_modules", "whole_course"} <= scopes
    assert {
        "semantic_duplication",
        "repeated_hook",
        "repeated_ending",
        "lost_prerequisite",
        "project_teaching_mismatch",
        "late_course_quality_decline",
        "generic_late_course_collapse",
        "phrase_drift",
        "contradiction",
    } <= codes


def test_cross_scope_serious_findings_are_export_blockers() -> None:
    course_map, reels = _healthy_case()
    broken_plan = course_map.modules[1].reels[0].model_copy(
        update={"prerequisite_lesson_ids": ["future-or-missing"]}
    )
    modules = list(course_map.modules)
    modules[1] = modules[1].model_copy(
        update={"reels": [broken_plan, modules[1].reels[1]]}
    )
    broken_map = course_map.model_copy(update={"modules": modules})

    export = evaluate_export_blockers(
        final_course=_final_course(broken_map, reels),
        course_map=broken_map,
        generated_reels=reels,
    )

    assert not export.ok
    assert any(blocker.code == "lost_prerequisite" for blocker in export.blockers)
