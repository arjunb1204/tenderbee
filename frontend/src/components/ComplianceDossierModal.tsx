"use client";

import React, { useState } from "react";
import { apiClient, ComplianceDossierRecord } from "@/lib/api";

interface ComplianceDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  dossier: ComplianceDossierRecord | null;
}

export default function ComplianceDossierModal({
  isOpen,
  onClose,
  dossier,
}: ComplianceDossierModalProps) {
  const [copiedHash, setCopiedHash] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  if (!isOpen || !dossier) return null;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(dossier.dossier_fingerprint);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleExportJSON = () => {
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(dossier, null, 2)
    )}`;
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", jsonString);
    downloadAnchor.setAttribute(
      "download",
      `tenderbee_compliance_dossier_${dossier.dossier_id}.json`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  /**
   * Direct PDF File Download:
   * Fetches the server-generated ReportLab binary PDF file directly.
   * Downloads in <50ms with zero reliance on browser print dialogs or detached iframes.
   */
  const handleDownloadPDF = async () => {
    setIsDownloadingPdf(true);
    try {
      const url = apiClient.verify.dossierPdfUrl(dossier.tender.id);
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to generate PDF (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `compliance_dossier_${dossier.dossier_id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      console.error("Direct PDF download error:", err);
      // Fallback: direct window location trigger
      window.location.href = apiClient.verify.dossierPdfUrl(dossier.tender.id);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  /**
   * Screen Print Handler:
   * Uses clean native window.print() paired with scoped @media print CSS
   * so only the dossier modal is sent to the printer with zero background leakage.
   */
  const handlePrint = () => {
    window.print();
  };

  const isReady = dossier.envelope_status === "READY FOR SUBMISSION";

  return (
    <>
      {/* Scoped print CSS ensuring ONLY this modal prints when window.print() is called */}
      <style>{`
        @media print {
          body {
            visibility: hidden !important;
            background: #ffffff !important;
          }
          #compliance-dossier-modal-overlay,
          #compliance-dossier-modal-overlay * {
            visibility: visible !important;
          }
          #compliance-dossier-modal-overlay {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            height: auto !important;
            background: #ffffff !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
            z-index: 999999 !important;
          }
          #compliance-dossier-print-container {
            max-height: none !important;
            overflow: visible !important;
            border: none !important;
            box-shadow: none !important;
            width: 100% !important;
            border-radius: 0 !important;
          }
          .print\\:hidden, .print-hidden {
            display: none !important;
          }
          .page-break-avoid {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
          }
        }
      `}</style>

      <div
        id="compliance-dossier-modal-overlay"
        className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 print:p-0 print:bg-white print:static"
      >
        {/* Modal Container */}
        <div
          id="compliance-dossier-print-container"
          className="bg-surface rounded-3xl shadow-2xl border border-outline-variant/30 max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200 print:max-h-none print:shadow-none print:border-none print:rounded-none"
        >
          {/* Header Bar */}
          <div className="bg-gradient-to-r from-primary via-primary-container to-primary text-on-primary p-5 sm:p-6 flex items-center justify-between gap-4 shrink-0 print:bg-none print:text-black print:border-b print:border-neutral-300">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center text-secondary-fixed border border-white/20 shadow-inner shrink-0 print:border-black">
                <span className="material-symbols-outlined text-2xl">verified_user</span>
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] uppercase font-bold tracking-widest bg-white/20 text-white px-2.5 py-0.5 rounded-full print:border print:border-black print:text-black">
                    Official Statutory Certification
                  </span>
                  <span className="text-xs text-white/80 print:text-neutral-600">
                    ID: <span className="font-mono font-bold text-white print:text-black">{dossier.dossier_id}</span>
                  </span>
                </div>
                <h2 className="font-serif text-xl sm:text-2xl font-bold tracking-tight mt-1 text-white print:text-black">
                  Government Procurement Compliance Dossier
                </h2>
              </div>
            </div>

            {/* Action Tools & Close */}
            <div className="flex items-center gap-2 print:hidden">
              <button
                type="button"
                onClick={handleDownloadPDF}
                disabled={isDownloadingPdf}
                title="Download Official PDF file"
                className="p-2 sm:px-3 sm:py-2 rounded-xl bg-secondary text-on-secondary hover:bg-secondary-container transition active:scale-95 cursor-pointer flex items-center gap-1.5 text-xs font-bold shadow-sm disabled:opacity-70"
              >
                <span className={`material-symbols-outlined text-base ${isDownloadingPdf ? "animate-spin" : ""}`}>
                  {isDownloadingPdf ? "progress_activity" : "download"}
                </span>
                <span className="hidden sm:inline">
                  {isDownloadingPdf ? "Downloading..." : "Download PDF"}
                </span>
              </button>

              <button
                type="button"
                onClick={handlePrint}
                title="Print Document"
                className="p-2 sm:px-3 sm:py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white transition active:scale-95 cursor-pointer flex items-center gap-1.5 text-xs font-semibold"
              >
                <span className="material-symbols-outlined text-base">print</span>
                <span className="hidden sm:inline">Print</span>
              </button>

              <button
                type="button"
                onClick={handleExportJSON}
                title="Download Verified JSON"
                className="p-2 sm:px-3 sm:py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white transition active:scale-95 cursor-pointer flex items-center gap-1.5 text-xs font-semibold"
              >
                <span className="material-symbols-outlined text-base">data_object</span>
                <span className="hidden sm:inline">JSON</span>
              </button>

              <button
                type="button"
                onClick={onClose}
                title="Close modal"
                className="w-9 h-9 rounded-xl bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition active:scale-95 cursor-pointer ml-1"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>
          </div>

          {/* Scrollable Content Body */}
          <div className="p-6 sm:p-8 overflow-y-auto space-y-6 text-on-surface print:overflow-visible">
            {/* Top Banner Status & Score */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-stretch page-break-avoid">
              {/* Status Card */}
              <div className="md:col-span-8 bg-surface-container-low rounded-2xl p-5 border border-outline-variant/30 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] uppercase tracking-wider font-bold text-on-surface-variant">
                      Envelope Locking Assessment
                    </span>
                    <span
                      className={`text-xs px-3 py-1 rounded-full font-bold flex items-center gap-1.5 ${
                        isReady
                          ? "bg-primary text-on-primary"
                          : "bg-error-container text-on-error-container"
                      }`}
                    >
                      <span className="material-symbols-outlined text-sm">
                        {isReady ? "lock_open" : "lock"}
                      </span>
                      {dossier.envelope_status}
                    </span>
                  </div>
                  <h3 className="font-serif text-lg font-bold text-primary mt-2">
                    {dossier.tender.title}
                  </h3>
                  <p className="text-xs text-on-surface-variant mt-1">
                    Procuring Authority: <strong className="text-on-surface">{dossier.tender.buyer_name}</strong> · Portal: <strong className="text-on-surface">{dossier.tender.portal}</strong>
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 mt-3 border-t border-outline-variant/20 text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">Notice Ref</span>
                    <span className="font-mono font-bold text-primary">{dossier.tender.tender_number}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">Estimated Value</span>
                    <span className="font-bold text-on-surface">₹{(dossier.tender.estimated_value_inr / 10000000).toFixed(2)} Cr</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">EMD Policy</span>
                    <span className="font-bold text-primary">{dossier.tender.mse_exemption}</span>
                  </div>
                </div>
              </div>

              {/* Score Ring / Badge */}
              <div className="md:col-span-4 bg-primary text-on-primary rounded-2xl p-5 flex flex-col items-center justify-center text-center relative overflow-hidden shadow-md">
                <div className="absolute top-0 right-0 w-32 h-32 bg-secondary/15 rounded-full blur-2xl pointer-events-none" />
                <span className="text-[10px] uppercase font-bold tracking-widest text-secondary-fixed">
                  Statutory Readiness Index
                </span>
                <div className="flex items-baseline gap-1 mt-2">
                  <span className="font-serif text-5xl font-extrabold text-white">
                    {dossier.compliance_score}
                  </span>
                  <span className="text-xl font-bold text-white/70">/ 100</span>
                </div>
                <span className="text-xs text-white/80 mt-1 font-medium">
                  {dossier.compliance_score >= 90
                    ? "Fully Verified & Compliant"
                    : "Action Required on Blockers"}
                </span>
                <div className="w-full bg-white/20 h-1.5 rounded-full mt-4 overflow-hidden">
                  <div
                    className="bg-secondary h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, dossier.compliance_score))}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Cryptographic Seal & Organization Credentials */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 page-break-avoid">
              {/* Bidder Profile */}
              <div className="bg-surface-container-lowest rounded-2xl p-5 border border-outline-variant/30 space-y-3">
                <div className="flex items-center gap-2 pb-2 border-b border-outline-variant/20">
                  <span className="material-symbols-outlined text-primary text-lg">domain</span>
                  <h4 className="font-serif text-sm font-bold text-primary">Certified Bidder Profile</h4>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">Legal Name:</span>
                    <span className="font-bold text-on-surface">{dossier.organization.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">GSTIN:</span>
                    <span className="font-mono font-bold text-primary">{dossier.organization.gstin}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">Udyam MSME:</span>
                    <span className="font-mono font-bold text-primary">{dossier.organization.udyam_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">PAN:</span>
                    <span className="font-mono font-bold text-on-surface">{dossier.organization.pan}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">Enterprise Category:</span>
                    <span className="font-bold text-secondary">{dossier.organization.category}</span>
                  </div>
                </div>
              </div>

              {/* Cryptographic Security Seal */}
              <div className="bg-surface-container-lowest rounded-2xl p-5 border border-outline-variant/30 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-outline-variant/20">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-lg">verified</span>
                    <h4 className="font-serif text-sm font-bold text-primary">FIPS 180-4 Security Seal</h4>
                  </div>
                  <span className="text-[10px] bg-secondary-fixed text-on-secondary-fixed px-2 py-0.5 rounded-full font-bold">
                    Immutable
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">Digest Algorithm</span>
                    <span className="font-semibold text-on-surface">{dossier.security_seal.algorithm}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">Root Authority</span>
                    <span className="text-on-surface">{dossier.security_seal.root_authority}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-on-surface-variant block">Canonical Fingerprint</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="font-mono text-[11px] bg-surface-container-high px-2 py-1 rounded text-primary break-all select-all flex-1">
                        {dossier.dossier_fingerprint}
                      </span>
                      <button
                        type="button"
                        onClick={handleCopyHash}
                        className="p-1 rounded hover:bg-surface-container text-on-surface-variant cursor-pointer print:hidden shrink-0"
                        title="Copy Hash"
                      >
                        <span className="material-symbols-outlined text-base">
                          {copiedHash ? "check" : "content_copy"}
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Statutory Rule Verdicts Breakdown */}
            <div className="bg-surface-container-lowest rounded-2xl p-5 border border-outline-variant/30 page-break-avoid">
              <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20 mb-3">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-lg">fact_check</span>
                  <h4 className="font-serif text-sm font-bold text-primary">
                    Deterministic Verification Results ({dossier.verdicts.length} Rules)
                  </h4>
                </div>
                <span className="text-[11px] text-on-surface-variant">
                  Evaluated: {new Date(dossier.generated_at).toLocaleString()}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-outline-variant/30 text-on-surface-variant font-semibold">
                      <th className="py-2.5 px-3">Rule ID</th>
                      <th className="py-2.5 px-3">Statutory Clause &amp; Subject</th>
                      <th className="py-2.5 px-3">Document Source</th>
                      <th className="py-2.5 px-3 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/20">
                    {dossier.verdicts.map((v, i) => {
                      const statusStr = (v.status || "").toUpperCase();
                      const isPass = ["READY", "PASS", "VERIFIED"].includes(statusStr);
                      return (
                        <tr key={v.rule_id || i} className="hover:bg-surface-container-low/50 transition">
                          <td className="py-3 px-3 font-mono font-bold text-primary">{v.rule_id}</td>
                          <td className="py-3 px-3">
                            <div className="font-semibold text-on-surface">{v.message}</div>
                            {v.clause && (
                              <div className="text-[11px] text-on-surface-variant italic mt-0.5">
                                {v.clause}
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-3 text-on-surface-variant font-mono">
                            {v.document_type || "Mandatory Tender Pack"}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span
                              className={`inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                                isPass
                                  ? "bg-primary/10 text-primary border border-primary/20"
                                  : "bg-error-container text-on-error-container"
                              }`}
                            >
                              <span className="material-symbols-outlined text-xs">
                                {isPass ? "check_circle" : "cancel"}
                              </span>
                              {isPass ? "PASSED" : "BLOCKER"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Attached Evidentiary Documents & Cryptographic Hashes */}
            {dossier.attached_documents && dossier.attached_documents.length > 0 && (
              <div className="bg-surface-container-lowest rounded-2xl p-5 border border-outline-variant/30 page-break-avoid">
                <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20 mb-3">
                  <span className="material-symbols-outlined text-primary text-lg">folder_open</span>
                  <h4 className="font-serif text-sm font-bold text-primary">
                    Attached Evidentiary Document Hashes ({dossier.attached_documents.length})
                  </h4>
                </div>
                <div className="space-y-2">
                  {dossier.attached_documents.map((doc, idx) => (
                    <div
                      key={doc.id || idx}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-surface-container-low text-xs border border-outline-variant/20"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-primary text-lg">picture_as_pdf</span>
                        <div>
                          <span className="font-bold text-on-surface">{doc.file_name}</span>
                          <div className="text-[10px] text-on-surface-variant">
                            Type: {doc.document_type} · Size: {doc.size_kb} KB · Signed:{" "}
                            <strong className={doc.is_digitally_signed ? "text-primary" : "text-error"}>
                              {doc.is_digitally_signed ? "YES (Class 3 DSC)" : "NO"}
                            </strong>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-on-surface-variant uppercase font-mono block">SHA-256 Digest</span>
                        <span className="font-mono text-[10px] text-primary break-all">{doc.sha256_hash}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Immutable Audit Ledger Records */}
            {dossier.audit_chain && dossier.audit_chain.length > 0 && (
              <div className="bg-surface-container-lowest rounded-2xl p-5 border border-outline-variant/30 page-break-avoid">
                <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20 mb-3">
                  <span className="material-symbols-outlined text-primary text-lg">history_edu</span>
                  <h4 className="font-serif text-sm font-bold text-primary">
                    Cryptographic Audit Chain (Recent Ledger Blocks)
                  </h4>
                </div>
                <div className="space-y-2 text-xs">
                  {dossier.audit_chain.map((entry, idx) => (
                    <div
                      key={entry.id || idx}
                      className="flex items-center justify-between gap-3 py-2 px-3 rounded-lg bg-surface-container-low/60 border border-outline-variant/20"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-on-surface-variant">#{idx + 1}</span>
                        <span className="font-bold text-on-surface">{entry.event_type}</span>
                        <span className="text-on-surface-variant">by {entry.actor}</span>
                      </div>
                      <div className="text-right font-mono text-[10px] text-primary">
                        {entry.payload_hash ? entry.payload_hash.slice(0, 16) + "..." : "Canonical Block"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Statutory Attestation */}
            <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs text-on-surface-variant leading-relaxed page-break-avoid">
              <strong className="text-primary font-serif block mb-1">Autonomous Legal &amp; Statutory Attestation:</strong>
              {dossier.legal_attestation}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="p-4 sm:p-5 bg-surface-container-lowest border-t border-outline-variant/30 flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0 print:hidden">
            <div className="flex items-center gap-2 text-xs text-on-surface-variant">
              <span className="material-symbols-outlined text-base text-primary">verified_user</span>
              <span>Tamper-evident verification certified by TenderBee Core</span>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                type="button"
                onClick={handleExportJSON}
                className="flex-1 sm:flex-initial px-3.5 py-2 rounded-full text-xs font-bold neu-button text-on-surface flex items-center justify-center gap-1.5 cursor-pointer active:scale-98"
              >
                <span className="material-symbols-outlined text-base">data_object</span>
                <span>JSON</span>
              </button>

              <button
                type="button"
                onClick={handlePrint}
                className="flex-1 sm:flex-initial px-3.5 py-2 rounded-full text-xs font-bold neu-button text-on-surface flex items-center justify-center gap-1.5 cursor-pointer active:scale-98"
              >
                <span className="material-symbols-outlined text-base">print</span>
                <span>Print</span>
              </button>

              <button
                type="button"
                onClick={handleDownloadPDF}
                disabled={isDownloadingPdf}
                className="flex-1 sm:flex-initial px-5 py-2.5 rounded-full text-xs font-bold neu-button-primary flex items-center justify-center gap-2 cursor-pointer active:scale-98 disabled:opacity-70 shadow-md"
              >
                <span className={`material-symbols-outlined text-base ${isDownloadingPdf ? "animate-spin" : ""}`}>
                  {isDownloadingPdf ? "progress_activity" : "download"}
                </span>
                <span>{isDownloadingPdf ? "Generating PDF..." : "Download Official PDF"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
