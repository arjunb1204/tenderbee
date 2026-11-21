"use client";

import React, { useState } from "react";
import { apiClient, ComplianceDossierRecord } from "@/lib/api";
import ComplianceDossierModal from "./ComplianceDossierModal";

interface AuditBottomBarProps {
  tenderId?: string;
}

export default function AuditBottomBar({ tenderId }: AuditBottomBarProps) {
  const [reAuditing, setReAuditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [dossier, setDossier] = useState<ComplianceDossierRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const handleReAudit = async () => {
    setReAuditing(true);
    setErrorNotice(null);
    try {
      if (tenderId) {
        await apiClient.verify.evaluate(tenderId);
      }
    } catch (err: any) {
      console.warn("Re-audit evaluation notice:", err);
    } finally {
      setTimeout(() => {
        setReAuditing(false);
      }, 900);
    }
  };

  const handleGenerateDossier = async () => {
    setGenerating(true);
    setErrorNotice(null);
    try {
      const res = await apiClient.verify.dossier(tenderId);
      if (res && (res.success || res.dossier_id)) {
        setDossier(res);
        setIsModalOpen(true);
      } else {
        throw new Error("Unable to compile dossier. Invalid response from engine.");
      }
    } catch (err: any) {
      console.error("Dossier generation error:", err);
      setErrorNotice(err?.message || "Failed to generate compliance dossier. Please retry.");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      <div className="bg-white/95 backdrop-blur-md rounded-2xl p-4 sm:p-5 shadow-[0_16px_40px_-10px_rgba(29,0,55,0.18)] border border-purple-100 flex flex-col md:flex-row items-center justify-between gap-4 sticky bottom-4 z-30 transition-all">
        {/* Status Warning Info */}
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-full bg-primary flex items-center justify-center text-on-primary shrink-0 shadow-sm">
            <span className="material-symbols-outlined text-xl">
              {dossier?.envelope_status === "READY FOR SUBMISSION" ? "verified" : "lock"}
            </span>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-serif text-lg sm:text-xl text-primary font-bold">
                {dossier
                  ? `Dossier Status: ${dossier.envelope_status}`
                  : "Envelope Lock: Statutory Audit Active"}
              </span>
              <span
                className={`text-[10px] px-2.5 py-0.5 rounded-full font-bold ${
                  dossier?.compliance_score && dossier.compliance_score >= 90
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "bg-error-container text-on-error-container"
                }`}
              >
                {dossier ? `${dossier.compliance_score}/100 Score` : "Pre-Submission"}
              </span>
            </div>
            <span className="text-xs text-on-surface-variant leading-snug mt-0.5">
              {errorNotice ? (
                <span className="text-error font-medium">{errorNotice}</span>
              ) : (
                "Deterministic verification compiles UDIN, CA Turnover, Udyam MSME, and GST into an immutable audit dossier."
              )}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 w-full md:w-auto flex-wrap sm:flex-nowrap shrink-0">
          <button
            onClick={handleReAudit}
            disabled={reAuditing}
            className="flex-1 sm:flex-initial bg-surface-container-low text-on-surface px-4 py-2.5 rounded-full text-xs font-bold flex items-center justify-center gap-2 hover:bg-surface-container transition-all cursor-pointer border border-outline-variant/30 active:scale-98 disabled:opacity-60"
            type="button"
          >
            <span className={`material-symbols-outlined text-base ${reAuditing ? "animate-spin" : ""}`}>
              refresh
            </span>
            <span>{reAuditing ? "Auditing Engine..." : "Run Final Re-Audit"}</span>
          </button>

          <button
            onClick={handleGenerateDossier}
            disabled={generating}
            className="flex-1 sm:flex-initial bg-primary text-on-primary px-5 py-2.5 rounded-full text-xs font-bold flex items-center justify-center gap-2 hover:bg-primary-container transition-all shadow-md hover:shadow-lg cursor-pointer active:scale-98 disabled:opacity-75 disabled:cursor-not-allowed"
            type="button"
          >
            <span className={`material-symbols-outlined text-base ${generating ? "animate-spin" : ""}`}>
              {generating ? "progress_activity" : "description"}
            </span>
            <span>{generating ? "Compiling Statutory Dossier..." : "Generate Compliance Dossier"}</span>
            {!generating && (
              <span className="w-6 h-6 rounded-full bg-secondary text-on-secondary flex items-center justify-center ml-1">
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Official Compliance Dossier Modal */}
      <ComplianceDossierModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        dossier={dossier}
      />
    </>
  );
}
