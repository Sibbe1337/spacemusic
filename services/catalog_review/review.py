"""Assigned-reviewer questions and owner replies; never an offer or rights check."""

from uuid import UUID, uuid4

from psycopg2.extras import Json

from .contracts import ReviewQuestion, ReviewReply
from .security import ReviewError, workspace_from_token


class ReviewConversation:
    def _conversation(self, db):
        db.execute(
            """SELECT q.question_id,q.body,q.created_at,q.request_documents,r.body AS reply_body,
            r.document_ids,r.created_at AS replied_at,
            s.supplement_id,s.version,s.submission_id,s.documents AS supplement_documents
            FROM review_questions q
            LEFT JOIN review_replies r USING(workspace_id,question_id)
            LEFT JOIN review_supplements s USING(workspace_id,question_id)
            ORDER BY q.created_at,q.question_id"""
        )
        return [
            {
                "question_id": str(row["question_id"]),
                "body": row["body"],
                "created_at": row["created_at"],
                "request_documents": row["request_documents"],
                "reply": (
                    {
                        "body": row["reply_body"],
                        "created_at": row["replied_at"],
                        "document_ids": row["document_ids"],
                        "supplement": (
                            {
                                "supplement_id": str(row["supplement_id"]),
                                "version": row["version"],
                                "submission_id": str(row["submission_id"]),
                                "documents": row["supplement_documents"],
                                "created_at": row["replied_at"],
                            }
                            if row["supplement_id"]
                            else None
                        ),
                    }
                    if row["replied_at"]
                    else None
                ),
            }
            for row in db.fetchall()
        ]

    def ask_question(self, token, value):
        item = ReviewQuestion.model_validate(value)
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._authorize(db, token)
            if member["role"] != "reviewer":
                raise ReviewError("reviewer_required", 403)
            db.execute("SELECT 1 FROM submissions")
            if not db.fetchone():
                raise ReviewError("submission_required")
            db.execute(
                "SELECT * FROM review_questions WHERE request_id=%s",
                (str(item.request_id),),
            )
            prior = db.fetchone()
            if prior:
                if (
                    prior["body"] != item.body
                    or prior["author_id"] != member["principal_id"]
                    or prior["request_documents"] != item.request_documents
                ):
                    raise ReviewError("message_request_conflict")
                return {"question_id": str(prior["question_id"]), "created": False}
            db.execute("SELECT count(*) AS count FROM review_questions")
            if db.fetchone()["count"] >= 20:
                raise ReviewError("question_limit_reached")
            question = str(uuid4())
            db.execute(
                """INSERT INTO review_questions
                (workspace_id,question_id,request_id,author_id,body,created_at,request_documents)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    workspace,
                    question,
                    str(item.request_id),
                    member["principal_id"],
                    item.body,
                    self.clock(),
                    item.request_documents,
                ),
            )
            self._audit(db, workspace, "review_question_asked")
            self._touch(db, workspace)
            return {"question_id": question, "created": True}

    def reply_to_question(self, token, question, value):
        item = ReviewReply.model_validate(value)
        question = str(UUID(str(question)))
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._authorize(db, token, owner=True)
            db.execute(
                "SELECT * FROM review_questions WHERE question_id=%s", (question,)
            )
            requested = db.fetchone()
            if not requested:
                raise ReviewError("question_unavailable", 404)
            db.execute(
                "SELECT * FROM review_replies WHERE question_id=%s OR request_id=%s",
                (question, str(item.request_id)),
            )
            prior = db.fetchone()
            if prior:
                if (
                    str(prior["question_id"]) == question
                    and str(prior["request_id"]) == str(item.request_id)
                    and prior["body"] == item.body
                    and prior["author_id"] == member["principal_id"]
                    and prior["document_ids"] == [str(d) for d in item.document_ids]
                ):
                    return {"question_id": question, "created": False}
                raise ReviewError("reply_locked")
            if item.document_ids and not requested["request_documents"]:
                raise ReviewError("document_request_required")
            documents = self._documents(db, item.document_ids, accepted=True)
            for doc in documents:
                if doc["question_id"] and str(doc["question_id"]) != question:
                    db.execute(
                        """SELECT 1 FROM review_supplements s,
                        jsonb_array_elements(s.documents) AS item
                        WHERE item->>'document_id'=%s""",
                        (str(doc["document_id"]),),
                    )
                    if not db.fetchone():
                        raise ReviewError("document_question_mismatch")
            db.execute(
                """INSERT INTO review_replies
                (workspace_id,question_id,request_id,author_id,body,created_at,document_ids)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    workspace,
                    question,
                    str(item.request_id),
                    member["principal_id"],
                    item.body,
                    self.clock(),
                    Json([str(d) for d in item.document_ids]),
                ),
            )
            if documents:
                db.execute("SELECT submission_id FROM submissions")
                submission = db.fetchone()["submission_id"]
                db.execute(
                    "SELECT COALESCE(max(version),0)+1 AS next FROM review_supplements"
                )
                version = db.fetchone()["next"]
                for doc in documents:
                    doc["document_id"] = str(doc["document_id"])
                    doc["question_id"] = (
                        str(doc["question_id"]) if doc["question_id"] else None
                    )
                db.execute(
                    "INSERT INTO review_supplements VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        workspace,
                        str(uuid4()),
                        version,
                        submission,
                        question,
                        Json(documents),
                        self.clock(),
                    ),
                )
            self._audit(db, workspace, "review_question_answered")
            self._touch(db, workspace)
            return {"question_id": question, "created": True}
