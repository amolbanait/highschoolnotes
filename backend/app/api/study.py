"""Quiz attempts and flashcard reviews. Recorded now so Phase 4 can find weak areas."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, own_guide
from app.core.errors import AppError, not_found
from app.db.models import FlashcardReview, QuizAttempt, User
from app.db.session import get_db
from app.pipeline.grounding import normalize
from app.schemas.api import FlashcardReviewIn, QuizAttemptIn, QuizAttemptOut

router = APIRouter(tags=["study"])


@router.post("/guides/{guide_id}/quiz-attempts", response_model=QuizAttemptOut)
def quiz_attempt(
    guide_id: uuid.UUID,
    body: QuizAttemptIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    guide = own_guide(db, user, guide_id)
    question = next(
        (q for q in (guide.content or {}).get("questions", []) if q["id"] == body.question_id), None
    )
    if question is None:
        raise not_found("question")
    # Multiple choice is graded here; open answers come back with the model answer for self-checking.
    is_correct = normalize(body.answer) == normalize(question["answer"]) if question["options"] else None
    db.add(
        QuizAttempt(
            user_id=user.id,
            guide_id=guide.id,
            question_id=body.question_id,
            answer=body.answer,
            is_correct=is_correct,
        )
    )
    db.commit()
    return {
        "is_correct": is_correct,
        "correct_answer": question["answer"],
        "explanation": question["explanation"],
        "source_refs": question["source_refs"],
    }


@router.post("/guides/{guide_id}/flashcard-reviews", status_code=201)
def flashcard_review(
    guide_id: uuid.UUID,
    body: FlashcardReviewIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    guide = own_guide(db, user, guide_id)
    if not any(c["id"] == body.card_id for c in (guide.content or {}).get("flashcards", [])):
        raise AppError(404, "not_found", "That flashcard does not exist.")
    db.add(FlashcardReview(user_id=user.id, guide_id=guide.id, card_id=body.card_id, rating=body.rating))
    db.commit()
    return Response(status_code=201)
