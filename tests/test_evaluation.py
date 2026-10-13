import json
import logging
from pathlib import Path
import pytest
from app.services.rag_service import RAGService, UNAVAILABLE_MESSAGE

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_run_comprehensive_evaluation(rag_service: RAGService, sample_docs_dir: Path):
    """Run full evaluation suite across the 12 evaluation test questions."""
    # 1. Ingest all available sample documents
    sample_files = [
        "ai_ethics_framework.md",
        "cloud_infrastructure_guide.txt",
        "quantum_computing_primer.txt",
        "enterprise_security_policy.pdf",
    ]

    ingested_count = 0
    for name in sample_files:
        file_path = sample_docs_dir / name
        if file_path.exists():
            rag_service.ingest_document(content=file_path.read_bytes(), filename=name)
            ingested_count += 1

    assert ingested_count >= 3, "At least 3 sample documents must be present for evaluation"

    # 2. Load evaluation dataset
    eval_file = Path(__file__).parent / "eval_dataset.json"
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    assert len(eval_cases) >= 10, "Evaluation dataset must contain at least 10 questions"

    total_cases = len(eval_cases)
    passed_cases = 0
    retrieval_hits = 0
    unanswerable_refusals = 0
    unanswerable_total = 0

    results_summary = []

    for case in eval_cases:
        qid = case["id"]
        question = case["question"]
        is_answerable = case["is_answerable"]
        expected_sources = case.get("expected_sources", [])

        # Execute query
        result = await rag_service.answer_question(question)

        # Check retrieval & answer validity
        retrieved_sources = list({e.document_name for e in result.evidence})

        if is_answerable:
            # Check if at least one expected source was retrieved
            source_matched = any(src in retrieved_sources for src in expected_sources)
            if source_matched:
                retrieval_hits += 1

            passed = source_matched and len(result.evidence) > 0
        else:
            unanswerable_total += 1
            # For unanswerable queries: must acknowledge missing info
            refused = (not result.is_answered) or (UNAVAILABLE_MESSAGE.lower() in result.answer.lower())
            if refused:
                unanswerable_refusals += 1
            passed = refused

        if passed:
            passed_cases += 1

        results_summary.append({
            "id": qid,
            "category": case["category"],
            "passed": passed,
            "is_answerable": is_answerable,
            "retrieved_sources": retrieved_sources,
            "confidence": result.confidence_score,
        })

    # Assertions
    retrieval_accuracy = retrieval_hits / (total_cases - unanswerable_total)
    refusal_accuracy = unanswerable_refusals / unanswerable_total if unanswerable_total > 0 else 1.0

    print("\n" + "=" * 50)
    print("EVALUATION BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Total Test Questions:        {total_cases}")
    print(f"Answerable Retrieval Recall: {retrieval_accuracy * 100:.1f}%")
    print(f"Unanswerable Rejection Rate: {refusal_accuracy * 100:.1f}%")
    print(f"Overall Test Pass Rate:      {(passed_cases / total_cases) * 100:.1f}%")
    print("=" * 50)

    assert refusal_accuracy >= 0.75, "Unanswerable questions should be reliably recognized and rejected."
    assert retrieval_accuracy >= 0.75, "Answerable questions should hit target documents."
