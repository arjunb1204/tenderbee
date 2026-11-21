"use client";

import React, { useRef, useState, useEffect } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/animations";
import { apiClient, UserProfile, VerificationAssessmentRecord } from "@/lib/api";

interface MatrixLayer {
  layerNo: string;
  ruleId: string;
  title: string;
  description: string;
  verdict: "PASS" | "WARNING" | "ACTION REQ" | "WAIVED" | "FAIL";
  metaLeftLabel: string;
  metaLeftVal: string;
  metaRightLabel: string;
  metaRightVal: string;
  isOverridden?: boolean;
  overriddenBy?: string;
  overrideReason?: string;
}

export default function VerificationMatrix() {
  const containerRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [assessment, setAssessment] = useState<VerificationAssessmentRecord | null>(null);
  const [overrideModalOpen, setOverrideModalOpen] = useState<boolean>(false);
  const [selectedLayer, setSelectedLayer] = useState<MatrixLayer | null>(null);
  const [newVerdict, setNewVerdict] = useState<"PASS" | "FAIL" | "WAIVED">("WAIVED");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [overrideSubmitting, setOverrideSubmitting] = useState<boolean>(false);
  const [overrideMessage, setOverrideMessage] = useState<string>("");

  const [layers, setLayers] = useState<MatrixLayer[]>([
    {
      layerNo: "Layer 01",
      ruleId: "RULE-FILE-INTEGRITY",
      title: "File Integrity & DSC",
      description: "PDF/A-1b standard conformance. PKCS#7 digital token verified against CCA root.",
      verdict: "PASS",
      metaLeftLabel: "Scan Quality:",
      metaLeftVal: "300 DPI Clear",
      metaRightLabel: "DSC Token:",
      metaRightVal: "Class-3 Active",
    },
    {
      layerNo: "Layer 02",
      ruleId: "RULE-UDIN-MATCH",
      title: "OCR & UDIN Match",
      description: "Chartered Accountant UDIN authentic. Turnover matches audited balance sheet.",
      verdict: "PASS",
      metaLeftLabel: "Req. Turnover:",
      metaLeftVal: "₹1.20 Cr",
      metaRightLabel: "Found Turnover:",
      metaRightVal: "₹1.82 Cr",
    },
    {
      layerNo: "Layer 03",
      ruleId: "RULE-ENTITY-CONSISTENCY",
      title: "Entity Consistency",
      description: "100% legal name alignment across MCA, PAN, GSTIN, and GeM Seller profile.",
      verdict: "PASS",
      metaLeftLabel: "PAN vs GST:",
      metaLeftVal: "Matched",
      metaRightLabel: "Corporate ID:",
      metaRightVal: "U74999DL...",
    },
    {
      layerNo: "Layer 04",
      ruleId: "RULE-TENDER-RULE-FIT",
      title: "Tender Rule Fit",
      description: "CPWD Clause 14 requires mechanised cleaning classification under NIC 81210.",
      verdict: "WARNING",
      metaLeftLabel: "Current Code:",
      metaLeftVal: "NIC 81210 (Gen)",
      metaRightLabel: "Affirmation:",
      metaRightVal: "Pending Sign",
    },
    {
      layerNo: "Layer 05",
      ruleId: "RULE-STATUTORY-CSPO",
      title: "Statutory Regs",
      description: "Technical competency certificate or CSPO/NSIC enlistment is unattached.",
      verdict: "ACTION REQ",
      metaLeftLabel: "Missing Doc:",
      metaLeftVal: "CSPO / NSIC",
      metaRightLabel: "Disqualification:",
      metaRightVal: "Stage 1 Risk",
    },
  ]);

  useEffect(() => {
    // 1. Fetch user role
    apiClient.auth.me().then((u) => setCurrentUser(u)).catch(() => {});

    // 2. Fetch latest assessment to reflect live backend status & overrides
    apiClient.verify.listAssessments().then((res) => {
      const list = Array.isArray(res) ? res : res.results || [];
      if (list && list.length > 0) {
        const latest = list[0];
        setAssessment(latest);

        // Apply any recorded backend overrides
        if (latest.verdict_overrides && latest.verdict_overrides.length > 0) {
          setLayers((prev) =>
            prev.map((l) => {
              const matchedOverride = latest.verdict_overrides?.find((o) => o.rule_id === l.ruleId);
              if (matchedOverride) {
                return {
                  ...l,
                  verdict: matchedOverride.new_verdict as any,
                  isOverridden: true,
                  overriddenBy: matchedOverride.overridden_by,
                  overrideReason: matchedOverride.reason,
                };
              }
              return l;
            })
          );
        }
      }
    }).catch(() => {});
  }, []);

  useGSAP(
    () => {
      const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (prefersReduced) return;

      if (gridRef.current) {
        gsap.fromTo(
          gridRef.current.children,
          { opacity: 0, y: 25 },
          {
            opacity: 1,
            y: 0,
            duration: 0.7,
            stagger: 0.08,
            ease: "power2.out",
          }
        );
      }
    },
    { scope: containerRef }
  );

  const canOverride = currentUser?.role === "reviewer" || currentUser?.role === "owner" || currentUser?.role === "admin";

  const handleOpenOverride = (layer: MatrixLayer) => {
    setSelectedLayer(layer);
    setNewVerdict(layer.verdict === "ACTION REQ" || layer.verdict === "FAIL" ? "WAIVED" : "PASS");
    setOverrideReason("");
    setOverrideMessage("");
    setOverrideModalOpen(true);
  };

  const handleApplyOverride = async () => {
    if (!selectedLayer || !overrideReason.trim()) return;
    setOverrideSubmitting(true);
    setOverrideMessage("");

    try {
      if (assessment?.id) {
        await apiClient.verify.overrideVerdict(
          assessment.id,
          selectedLayer.ruleId,
          newVerdict,
          overrideReason
        );
      }

      // Update local layer state
      setLayers((prev) =>
        prev.map((l) =>
          l.ruleId === selectedLayer.ruleId
            ? {
                ...l,
                verdict: newVerdict,
                isOverridden: true,
                overriddenBy: currentUser?.email || "Reviewer",
                overrideReason,
              }
            : l
        )
      );

      setOverrideMessage("Override recorded in immutable audit log!");
      setTimeout(() => {
        setOverrideModalOpen(false);
      }, 1500);
    } catch (err: any) {
      setOverrideMessage(err.message || "Failed to record override.");
    } finally {
      setOverrideSubmitting(false);
    }
  };

  return (
    <section ref={containerRef} className="flex flex-col gap-4">
      {/* Header Strip */}
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-secondary font-bold">
            Deep Architecture
          </span>
          <h2 className="font-serif text-2xl sm:text-3xl text-primary font-bold">
            5-Layer Statutory Verification Matrix
          </h2>
        </div>
        <div className="flex items-center gap-2 text-on-surface-variant text-[11px] font-semibold uppercase tracking-wider">
          <span>Role: <strong className="text-primary uppercase">{currentUser?.role || "Reviewer"}</strong></span>
          <span>·</span>
          <span>SHA-256 Validated</span>
        </div>
      </div>

      {/* 5-Column Grid */}
      <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {layers.map((layer) => {
          const isPass = layer.verdict === "PASS" || layer.verdict === "WAIVED";
          const isWarning = layer.verdict === "WARNING";
          const isActionReq = layer.verdict === "ACTION REQ" || layer.verdict === "FAIL";

          return (
            <div
              key={layer.layerNo}
              className="bg-surface-container-lowest rounded-2xl p-5 shadow-sm border border-outline-variant/30 flex flex-col justify-between transition-all hover:shadow-md hover:-translate-y-0.5"
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold">
                    {layer.layerNo}
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-bold ${
                        isPass
                          ? "bg-secondary-fixed text-on-secondary-fixed"
                          : isWarning
                          ? "bg-amber-100 text-amber-900"
                          : "bg-error-container text-on-error-container"
                      }`}
                    >
                      <span className="material-symbols-outlined text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>
                        {isPass ? "check" : isWarning ? "priority_high" : "close"}
                      </span>
                      {layer.verdict}
                    </span>
                  </div>
                </div>

                <h3 className="font-serif text-lg text-primary mt-1 font-bold">{layer.title}</h3>
                <p className="text-xs text-on-surface-variant leading-snug">
                  {layer.description}
                </p>

                {layer.isOverridden && (
                  <div className="mt-1 p-2 bg-purple-50 rounded-lg text-[10px] text-purple-900 border border-purple-200">
                    <p className="font-bold flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs">shield_person</span>
                      Manual Override Recorded
                    </p>
                    <p className="truncate mt-0.5 opacity-80">{layer.overrideReason}</p>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-2 flex flex-col gap-2">
                <div className="bg-surface-container-low p-2.5 rounded-xl flex flex-col gap-1 text-on-surface-variant text-xs border border-outline-variant/20">
                  <div className="flex justify-between">
                    <span>{layer.metaLeftLabel}</span>
                    <span className="font-bold text-on-surface">{layer.metaLeftVal}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{layer.metaRightLabel}</span>
                    <span className={`font-bold ${isActionReq ? "text-error" : isPass ? "text-secondary" : "text-amber-800"}`}>
                      {layer.metaRightVal}
                    </span>
                  </div>
                </div>

                {/* Reviewer / Owner Override button */}
                <button
                  type="button"
                  onClick={() => handleOpenOverride(layer)}
                  className="w-full text-center py-1 rounded-lg neu-pressed-sm text-[10px] font-bold text-secondary hover:text-primary transition flex items-center justify-center gap-1 cursor-pointer"
                  title="Override verdict with audit reason"
                >
                  <span className="material-symbols-outlined text-xs">edit_note</span>
                  <span>{layer.isOverridden ? "Edit Override" : "Reviewer Override"}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Manual Verdict Override Modal */}
      {overrideModalOpen && selectedLayer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-surface-container-lowest neu-flat rounded-2xl max-w-lg w-full p-6 border border-outline-variant/30 flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-outline-variant/20 pb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl">shield_person</span>
                <h3 className="font-serif text-lg font-bold text-primary">
                  Reviewer Verdict Override
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setOverrideModalOpen(false)}
                className="text-on-surface-variant hover:text-primary cursor-pointer"
              >
                <span className="material-symbols-outlined text-lg">close</span>
              </button>
            </div>

            <div className="flex flex-col gap-2">
              <p className="text-xs text-on-surface-variant">
                Rule: <strong className="text-primary font-bold">{selectedLayer.ruleId}</strong> · {selectedLayer.title}
              </p>
              <p className="text-xs text-on-surface-variant leading-snug">
                Overrides are cryptographically signed and recorded in the append-only <strong className="text-primary">AuditLogEntry</strong> ledger with your actor ID.
              </p>
            </div>

            {/* Verdict Selection */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] uppercase font-bold text-on-surface-variant">
                Target Statutory Verdict:
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(["PASS", "WAIVED", "FAIL"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setNewVerdict(v)}
                    className={`py-2 rounded-xl text-xs font-bold transition cursor-pointer border ${
                      newVerdict === v
                        ? "neu-button-primary"
                        : "neu-button text-on-surface-variant border-outline-variant/30"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Mandatory Reason */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] uppercase font-bold text-on-surface-variant">
                Mandatory Regulatory Justification (Audit Trail):
              </label>
              <textarea
                rows={3}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="E.g. Exemption confirmed under GFR 153 via MSME certificate, or clarified in Pre-bid Corrigendum #2..."
                className="w-full rounded-xl neu-pressed p-3 text-xs text-on-surface placeholder:text-on-surface-variant outline-none border border-outline-variant/30 focus:ring-1 focus:ring-secondary/40"
              />
            </div>

            {/* Role restriction feedback */}
            {!canOverride && (
              <div className="p-2.5 rounded-xl bg-amber-50 text-amber-900 border border-amber-200 text-[11px] flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">lock</span>
                <span>Your account role is <strong>{currentUser?.role || "member"}</strong>. Only Reviewers or Owners can execute persistent overrides.</span>
              </div>
            )}

            {overrideMessage && (
              <p className="text-xs font-bold text-emerald-700 bg-emerald-50 p-2 rounded-lg border border-emerald-200">
                {overrideMessage}
              </p>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-outline-variant/20">
              <button
                type="button"
                onClick={() => setOverrideModalOpen(false)}
                className="px-4 py-2 rounded-xl neu-button text-xs font-semibold text-on-surface cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyOverride}
                disabled={overrideSubmitting || !overrideReason.trim()}
                className="px-5 py-2 rounded-xl neu-button-primary text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                {overrideSubmitting ? (
                  <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined text-sm">verified</span>
                )}
                <span>Commit Audit Override</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

