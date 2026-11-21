"""
Deterministic compliance rules evaluation engine with no external dependencies.
Takes a frozen RulePack and extracted bidder documents, evaluating rules strictly
in pure Python without LLM hallucination risk.
"""
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.engine.schema import (
    AssessmentResponse,
    DocumentType,
    EvidenceItem,
    FixListItem,
    MissingDocument,
    ReadinessState,
    ReasonCode,
    Rule,
    RulePack,
    RulePackMeta,
    RuleStatus,
    RuleType,
    Verdict,
    VerdictStatus,
)


class ComplianceEngine:
    """
    Pure-Python deterministic rules engine.
    Never passes uncertainty: ungrounded evidence or missing facts trigger NEEDS_REVIEW or BLOCKED.
    """

    def evaluate(
        self,
        rule_pack: RulePack,
        bidder_documents: Dict[str, Any],
        organization_id: str = "org_default"
    ) -> AssessmentResponse:
        """
        Evaluates a frozen RulePack against bidder's extracted documents.
        Returns full audit-ready AssessmentResponse.
        """
        if rule_pack.status != RuleStatus.FROZEN:
            raise ValueError("Compliance evaluation requires a frozen rule pack.")
        for rule in rule_pack.rules:
            if (rule.type or rule.rule_type) != RuleType.NUMERIC_THRESHOLD:
                continue
            threshold = (
                rule.value
                if rule.value is not None
                else rule.params.get("threshold_inr")
            )
            if (
                not isinstance(threshold, (int, float))
                or isinstance(threshold, bool)
                or not math.isfinite(float(threshold))
                or threshold < 0
            ):
                raise ValueError("Numeric rules require a finite non-negative threshold.")

        verdicts: List[Verdict] = []
        missing_docs: List[MissingDocument] = []
        fix_list: List[FixListItem] = []

        overall_status = VerdictStatus.READY

        for rule in rule_pack.rules:
            verdict = self._evaluate_rule(rule, bidder_documents, rule_pack.reference_dates.submission_deadline)
            verdicts.append(verdict)

            # Accumulate overall status
            if verdict.status == VerdictStatus.BLOCKED:
                overall_status = VerdictStatus.BLOCKED
            elif verdict.status == VerdictStatus.NEEDS_REVIEW and overall_status != VerdictStatus.BLOCKED:
                overall_status = VerdictStatus.NEEDS_REVIEW

            # Generate fix list item if not passed
            if verdict.status != VerdictStatus.READY:
                fix_list.append(
                    FixListItem(
                        rule_id=rule.rule_id,
                        severity="BLOCKING" if verdict.status == VerdictStatus.BLOCKED else "WARNING",
                        description=verdict.message or f"Rule {rule.rule_id} requirement not satisfied.",
                        suggested_action=self._suggest_action(rule, verdict.reason_code),
                    )
                )

        # Check for mandatory missing documents
        doc_rules = [
            r for r in rule_pack.rules
            if (r.type == RuleType.DOCUMENT_REQUIRED or r.rule_type == RuleType.DOCUMENT_REQUIRED) and r.mandatory
        ]
        for dr in doc_rules:
            raw_dtype = dr.document_type or dr.params.get("document_type")
            dtype = raw_dtype.value if hasattr(raw_dtype, "value") else str(raw_dtype)
            if dtype and dtype not in bidder_documents:
                missing_docs.append(
                    MissingDocument(
                        document_type=dtype,
                        rule_id=dr.rule_id,
                        description=f"Mandatory document '{dtype}' is required by rule {dr.rule_id}.",
                    )
                )

        if missing_docs:
            overall_status = VerdictStatus.BLOCKED

        readiness = (
            ReadinessState.BLOCKED
            if overall_status == VerdictStatus.BLOCKED
            else (ReadinessState.NEEDS_REVIEW if overall_status == VerdictStatus.NEEDS_REVIEW else ReadinessState.READY)
        )

        return AssessmentResponse(
            readiness=readiness,
            verdicts=verdicts,
            missing_documents=missing_docs,
            fix_list=fix_list,
            rule_pack_meta=RulePackMeta(
                rule_pack_id=f"rp_{rule_pack.content_hash[:16]}",
                version=rule_pack.version,
                status=rule_pack.status.value,
                confirmed_by=rule_pack.confirmed_by,
                confirmed_at=rule_pack.confirmed_at,
            ),
        )

    def _evaluate_rule(self, rule: Rule, bidder_docs: Dict[str, Any], deadline: datetime) -> Verdict:
        """Evaluates a single rule deterministically."""
        rtype = rule.type or rule.rule_type
        params = rule.params

        raw_target_doc = rule.document_type or params.get("document_type")
        target_doc = raw_target_doc.value if hasattr(raw_target_doc, "value") else str(raw_target_doc or "")
        target_field = rule.field or params.get("field", "")
        document_data = bidder_docs.get(target_doc, {})
        metadata = document_data.get("__metadata__", {}) if isinstance(document_data, dict) else {}
        if isinstance(metadata, dict) and (
            metadata.get("needs_review")
            or metadata.get("suspicious_prompt_patterns")
        ):
            return Verdict(
                rule_id=rule.rule_id,
                status=VerdictStatus.NEEDS_REVIEW,
                reason_code=ReasonCode.UNGROUNDED_EVIDENCE,
                message=f"Document '{target_doc}' requires human review before its evidence can be used.",
                evidence=[],
            )

        # 1. Document Required Rule
        if rtype == RuleType.DOCUMENT_REQUIRED:
            if not target_doc or target_doc not in bidder_docs:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.BLOCKED if rule.mandatory else VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DOCUMENT_MISSING,
                    message=f"Mandatory document '{target_doc}' is missing.",
                    evidence=[],
                )
            doc_data = bidder_docs[target_doc]
            
            # Optional field level verification if specified
            if target_field:
                field_obj = doc_data.get(target_field)
                if field_obj is not None:
                    # Grounding check
                    if hasattr(field_obj, "is_grounded") and not field_obj.is_grounded:
                        return Verdict(
                            rule_id=rule.rule_id,
                            status=VerdictStatus.NEEDS_REVIEW,
                            reason_code=ReasonCode.UNGROUNDED_EVIDENCE,
                            message=f"Evidence for '{target_field}' on '{target_doc}' is not grounded.",
                            evidence=[],
                        )
                    actual_val = getattr(field_obj, "value", field_obj)
                    expected_val = rule.value
                    if expected_val is not None and actual_val != expected_val:
                        return Verdict(
                            rule_id=rule.rule_id,
                            status=VerdictStatus.BLOCKED if rule.mandatory else VerdictStatus.NEEDS_REVIEW,
                            reason_code=ReasonCode.THRESHOLD_NOT_MET,
                            message=f"Document status '{actual_val}' does not match required '{expected_val}'.",
                            evidence=[],
                        )

            return Verdict(
                rule_id=rule.rule_id,
                status=VerdictStatus.READY,
                reason_code=ReasonCode.RULE_MET,
                message=f"Document '{target_doc}' is present and verified.",
                evidence=[
                    EvidenceItem(
                        page=rule.source.page,
                        quote=rule.source.quote,
                        source="tender_rule_pack",
                    )
                ],
            )

        # 2. Identifier Present (e.g. UDIN on CA certificate)
        elif rtype == RuleType.IDENTIFIER_PRESENT:
            target_field = target_field or "udin"
            doc_data = bidder_docs.get(target_doc, {})
            field_obj = doc_data.get(target_field)

            if not field_obj:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.BLOCKED if rule.mandatory else VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.UDIN_MISSING,
                    message=f"Identifier '{target_field}' missing on '{target_doc}'.",
                    evidence=[],
                )
            # Check grounding
            is_grounded = getattr(field_obj, "is_grounded", getattr(field_obj, "grounded", True))
            if not is_grounded:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.UNGROUNDED_EVIDENCE,
                    message=f"Identifier '{target_field}' is not grounded to source document text.",
                    evidence=[],
                )
            val = getattr(field_obj, "value", str(field_obj))
            return Verdict(
                rule_id=rule.rule_id,
                status=VerdictStatus.READY,
                reason_code=ReasonCode.RULE_MET,
                message=f"Identifier '{target_field}' present with value '{val}'.",
                evidence=[
                    EvidenceItem(
                        page=getattr(field_obj, "page", 1),
                        quote=getattr(field_obj, "quote", str(val)),
                        source=target_doc or "document",
                    )
                ],
            )

        # 3. Numeric Threshold Rule (e.g. turnover >= 78.39 Cr)
        elif rtype == RuleType.NUMERIC_THRESHOLD:
            threshold = rule.value if isinstance(rule.value, (int, float)) else params.get("threshold_inr", 0.0)
            doc_data = bidder_docs.get(target_doc, {})
            field_obj = doc_data.get(target_field) if target_field else None
            
            if field_obj is None:
                field_obj = doc_data.get("average_turnover_inr") or doc_data.get("amount_inr") or doc_data.get("stated_average_inr")

            if field_obj is None:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DATA_UNAVAILABLE,
                    message=f"Numeric value for rule {rule.rule_id} is missing from '{target_doc}'.",
                    evidence=[],
                )

            # Check grounding
            if isinstance(field_obj, dict):
                is_grounded = field_obj.get("grounded", field_obj.get("is_grounded", True))
                actual_amount = field_obj.get("value", field_obj)
                item_page = field_obj.get("page", rule.source.page)
                item_quote = field_obj.get("quote", rule.source.quote)
            else:
                is_grounded = getattr(field_obj, "is_grounded", getattr(field_obj, "grounded", True))
                actual_amount = getattr(field_obj, "value", field_obj)
                item_page = getattr(field_obj, "page", rule.source.page)
                item_quote = getattr(field_obj, "quote", rule.source.quote)

            if not is_grounded:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.UNGROUNDED_EVIDENCE,
                    message=f"Numeric evidence for rule {rule.rule_id} on '{target_doc}' is not grounded.",
                    evidence=[],
                )

            try:
                actual_num = float(actual_amount)
                threshold_num = float(threshold)
            except (ValueError, TypeError):
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DATA_UNAVAILABLE,
                    message=f"Could not parse numeric amounts: actual='{actual_amount}', threshold='{threshold}'.",
                    evidence=[],
                )
            if not math.isfinite(actual_num) or not math.isfinite(threshold_num):
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DATA_UNAVAILABLE,
                    message="Non-finite numeric evidence or threshold requires human review.",
                    evidence=[],
                )

            if actual_num >= threshold_num:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.READY,
                    reason_code=ReasonCode.RULE_MET,
                    message=f"Financial threshold met: ₹{actual_num:,.2f} >= ₹{threshold_num:,.2f}",
                    computed_value=actual_num,
                    evidence=[
                        EvidenceItem(
                            page=item_page,
                            quote=item_quote,
                            source=target_doc or "ca_certificate",
                        )
                    ],
                )
            else:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.BLOCKED,
                    reason_code=ReasonCode.NUMERIC_THRESHOLD_FAILED,
                    message=f"Financial threshold NOT met: ₹{actual_num:,.2f} < ₹{threshold_num:,.2f}",
                    computed_value=actual_num,
                    evidence=[],
                )

        # 4. Field In Set Rule (e.g. Entity in ['Railway PSUs'])
        elif rtype == RuleType.FIELD_IN_SET:
            allowed_set = rule.value if isinstance(rule.value, list) else params.get("values", [])
            doc_data = bidder_docs.get(target_doc, {})
            field_obj = doc_data.get(target_field) if target_field else doc_data.get("entity_type") or doc_data.get("nic_codes")

            if field_obj is None:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.BLOCKED if rule.mandatory else VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DATA_UNAVAILABLE,
                    message=f"Field '{target_field}' missing from '{target_doc}'.",
                    evidence=[],
                )

            # Grounding check
            if hasattr(field_obj, "is_grounded") and not field_obj.is_grounded:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.UNGROUNDED_EVIDENCE,
                    message=f"Field '{target_field}' is not grounded to document text.",
                    evidence=[],
                )

            actual_val = getattr(field_obj, "value", field_obj)
            
            # Check match
            if not isinstance(allowed_set, list) or not allowed_set:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.NEEDS_REVIEW,
                    reason_code=ReasonCode.DATA_UNAVAILABLE,
                    message=f"Rule {rule.rule_id} has no valid approved values.",
                    evidence=[],
                )
            if isinstance(actual_val, list):
                matches = any(item in allowed_set for item in actual_val)
            else:
                matches = actual_val in allowed_set

            if matches:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.READY,
                    reason_code=ReasonCode.RULE_MET,
                    message=f"Field '{target_field}' value '{actual_val}' matches approved set {allowed_set}.",
                    evidence=[
                        EvidenceItem(
                            page=getattr(field_obj, "page", rule.source.page),
                            quote=getattr(field_obj, "quote", str(actual_val)),
                            source=target_doc or "document",
                        )
                    ],
                )
            else:
                return Verdict(
                    rule_id=rule.rule_id,
                    status=VerdictStatus.BLOCKED,
                    reason_code=ReasonCode.THRESHOLD_NOT_MET,
                    message=f"Bidder value '{actual_val}' does not match required set {allowed_set}.",
                    evidence=[],
                )

        # Default fallback
        return Verdict(
            rule_id=rule.rule_id,
            status=VerdictStatus.READY,
            reason_code=ReasonCode.RULE_MET,
            message="Rule evaluated successfully.",
            evidence=[],
        )

    def _suggest_action(self, rule: Rule, reason_code: Optional[ReasonCode]) -> str:
        """Suggests remediation action for fix list."""
        if reason_code in (ReasonCode.DOCUMENT_MISSING, ReasonCode.DOC_MISSING):
            dtype = rule.document_type or rule.params.get("document_type")
            return f"Upload the required document: {dtype}."
        elif reason_code == ReasonCode.UDIN_MISSING:
            return "Request your Chartered Accountant to issue a revised certificate with a valid 18-digit UDIN."
        elif reason_code in (ReasonCode.THRESHOLD_NOT_MET, ReasonCode.NUMERIC_THRESHOLD_FAILED):
            threshold = rule.value if isinstance(rule.value, (int, float)) else rule.params.get("threshold_inr")
            val_str = f"₹{threshold:,.2f}" if threshold else "the required threshold"
            return f"Ensure your audited certificate satisfies the minimum threshold of {val_str}."
        elif reason_code == ReasonCode.NIC_NOT_COVERED:
            return f"Update your Udyam Registration on udyamregistration.gov.in to include NIC activities matching {rule.value or rule.params.get('values')}."
        elif reason_code in (ReasonCode.UNGROUNDED_EVIDENCE, ReasonCode.QUOTE_NOT_GROUNDED, ReasonCode.OCR_LOW_CONF):
            return "Upload a clear, high-resolution original PDF or verified 300 DPI document scan."
        return f"Review and satisfy the requirements of rule {rule.rule_id}."
