"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import AuditHeaderStrip from "@/components/AuditHeaderStrip";
import ReadinessGaugeCard from "@/components/ReadinessGaugeCard";
import RegulatoryBento from "@/components/RegulatoryBento";
import VerificationMatrix from "@/components/VerificationMatrix";
import RemediationRoadmap from "@/components/RemediationRoadmap";
import EvidenceInspector from "@/components/EvidenceInspector";
import AuditBottomBar from "@/components/AuditBottomBar";
import { apiClient, AuditEntry } from "@/lib/api";

export default function AuditPage() {
  const [activeTab, setActiveTab] = useState<"scorecard" | "ledger">("scorecard");
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [filterEventType, setFilterEventType] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedEntryDetails, setSelectedEntryDetails] = useState<AuditEntry | null>(null);
  const [isLoadingLedger, setIsLoadingLedger] = useState<boolean>(false);
  const [selectedTenderId, setSelectedTenderId] = useState<string>("gem-992140");

  const fetchLedger = () => {
    setIsLoadingLedger(true);
    apiClient.audit
      .list()
      .then((res) => {
        const list = Array.isArray(res) ? res : res.results || [];
        setAuditEntries(list);
      })
      .catch(() => {})
      .finally(() => setIsLoadingLedger(false));
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  const filteredEntries = auditEntries.filter((entry) => {
    const matchesType = filterEventType === "ALL" || entry.event_type === filterEventType;
    const matchesSearch =
      entry.actor.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entry.target_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entry.payload_hash.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  return (
    <div className="bg-surface font-sans text-on-surface antialiased min-h-screen">
      {/* Sidebar Navigation */}
      <Sidebar activeTab="audit" />

      {/* Main Content Area */}
      <div className="lg:pl-72 flex flex-col min-h-screen">
        <DashboardHeader />

        <main className="w-full pt-16 bg-surface min-h-screen">
          <div className="px-4 sm:px-8 lg:px-10 py-6 flex flex-col gap-6 max-w-[1440px] mx-auto w-full pb-36">
            {/* View Mode Switcher Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-outline-variant/30 pb-4">
              <div>
                <span className="text-[10px] uppercase font-bold text-secondary tracking-widest block">
                  Statutory Assurance Hub
                </span>
                <h1 className="font-serif text-2xl sm:text-3xl text-primary font-bold mt-0.5">
                  Autonomous Tender Audit &amp; Ledger
                </h1>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("scorecard")}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                    activeTab === "scorecard"
                      ? "neu-button-primary"
                      : "neu-button text-on-surface-variant"
                  }`}
                >
                  <span className="material-symbols-outlined text-base">fact_check</span>
                  <span>Compliance Scorecard</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("ledger")}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer relative ${
                    activeTab === "ledger"
                      ? "neu-button-primary"
                      : "neu-button text-on-surface-variant"
                  }`}
                >
                  <span className="material-symbols-outlined text-base">history_edu</span>
                  <span>Immutable Audit Ledger</span>
                  {auditEntries.length > 0 && (
                    <span className="text-[10px] bg-secondary-fixed text-on-secondary-fixed px-1.5 py-0.2 rounded-full font-bold">
                      {auditEntries.length}
                    </span>
                  )}
                </button>
              </div>
            </div>

            {/* TAB 1: Scorecard View */}
            {activeTab === "scorecard" && (
              <div className="flex flex-col gap-6">
                {/* Section 1: Tender Context Selector & Header Strip */}
                <AuditHeaderStrip
                  selectedBid={selectedTenderId}
                  onSelectBid={(id) => setSelectedTenderId(id)}
                />

                {/* Section 2: Primary Scorecard & Rule Bento */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                  <div className="lg:col-span-8">
                    <ReadinessGaugeCard />
                  </div>
                  <div className="lg:col-span-4">
                    <RegulatoryBento />
                  </div>
                </section>

                {/* Section 3: 5-Layer Statutory Verification Matrix */}
                <VerificationMatrix />

                {/* Section 4 & 5: Remediation Roadmap & Evidence Inspector Split */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  <div className="lg:col-span-7">
                    <RemediationRoadmap />
                  </div>
                  <div className="lg:col-span-5">
                    <EvidenceInspector />
                  </div>
                </div>

                {/* Section 6: Sticky Submission Bottom Action Bar */}
                <AuditBottomBar tenderId={selectedTenderId} />
              </div>
            )}

            {/* TAB 2: Immutable Ledger View */}
            {activeTab === "ledger" && (
              <div className="flex flex-col gap-6">
                {/* Filter and Search Bar */}
                <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {["ALL", "ASSESSMENT_EVALUATED", "DOCUMENT_UPLOAD", "VERDICT_OVERRIDE", "RULE_PACK_FROZEN", "LOGIN_SUCCESS"].map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setFilterEventType(t)}
                        className={`text-[10px] font-bold px-3 py-1.5 rounded-full transition cursor-pointer ${
                          filterEventType === t
                            ? "neu-button-primary"
                            : "neu-button text-on-surface-variant"
                        }`}
                      >
                        {t === "ALL" ? "All Events" : t.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="relative w-full sm:w-64">
                      <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-sm text-on-surface-variant">
                        search
                      </span>
                      <input
                        type="text"
                        placeholder="Search actor, target, hash..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full rounded-xl neu-pressed py-2 pl-9 pr-3 text-xs font-medium text-on-surface placeholder:text-on-surface-variant outline-none"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={fetchLedger}
                      disabled={isLoadingLedger}
                      className="p-2 rounded-xl neu-button text-on-surface-variant hover:text-primary transition cursor-pointer"
                      title="Refresh Ledger"
                    >
                      <span className={`material-symbols-outlined text-base ${isLoadingLedger ? "animate-spin" : ""}`}>
                        refresh
                      </span>
                    </button>
                  </div>
                </div>

                {/* Ledger Table */}
                <div className="bg-surface-container-lowest neu-flat rounded-2xl overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-outline-variant/30 bg-surface-container-low font-bold text-on-surface-variant uppercase text-[10px]">
                          <th className="px-5 py-3.5">TIMESTAMP (IST)</th>
                          <th className="px-4 py-3.5">EVENT TYPE</th>
                          <th className="px-4 py-3.5">ACTOR</th>
                          <th className="px-4 py-3.5">TARGET IDENTIFIER</th>
                          <th className="px-4 py-3.5">SHA-256 DIGEST</th>
                          <th className="px-5 py-3.5 text-right">ACTION</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-outline-variant/20">
                        {filteredEntries.map((entry) => (
                          <tr key={entry.id} className="hover:bg-surface-container-low/50 transition-colors">
                            <td className="px-5 py-3.5 text-on-surface-variant whitespace-nowrap">
                              {new Date(entry.timestamp).toLocaleString("en-IN", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                                hour12: false,
                              })}
                            </td>

                            <td className="px-4 py-3.5">
                              <span
                                className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  entry.event_type.includes("OVERRIDE")
                                    ? "bg-purple-100 text-purple-900 border border-purple-200"
                                    : entry.event_type.includes("DOCUMENT")
                                    ? "bg-indigo-100 text-indigo-900 border border-indigo-200"
                                    : entry.event_type.includes("ASSESSMENT")
                                    ? "bg-emerald-100 text-emerald-900 border border-emerald-200"
                                    : "bg-surface-container-high text-on-surface"
                                }`}
                              >
                                {entry.event_type}
                              </span>
                            </td>

                            <td className="px-4 py-3.5 text-primary font-bold">
                              {entry.actor}
                            </td>

                            <td className="px-4 py-3.5 text-on-surface-variant truncate max-w-[180px]">
                              {entry.target_id}
                            </td>

                            <td className="px-4 py-3.5 text-secondary font-mono text-[11px]">
                              {entry.payload_hash ? `${entry.payload_hash.slice(0, 16)}...` : "SHA-256 Chain"}
                            </td>

                            <td className="px-5 py-3.5 text-right">
                              <button
                                type="button"
                                onClick={() => setSelectedEntryDetails(entry)}
                                className="px-2.5 py-1 rounded-lg neu-button text-[10px] font-bold text-secondary hover:text-primary transition cursor-pointer"
                              >
                                Inspect Payload
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {filteredEntries.length === 0 && (
                    <div className="p-12 text-center text-xs text-on-surface-variant">
                      No cryptographic audit entries recorded yet. Evaluated assessments, uploaded documents, and reviewer overrides will appear here permanently.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Entry Details Modal */}
            {selectedEntryDetails && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
                <div className="bg-surface-container-lowest neu-flat rounded-2xl max-w-xl w-full p-6 border border-outline-variant/30 flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-200">
                  <div className="flex items-center justify-between border-b border-outline-variant/20 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-secondary text-xl">verified</span>
                      <h3 className="font-serif text-lg font-bold text-primary">
                        Cryptographic Audit Entry Details
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedEntryDetails(null)}
                      className="text-on-surface-variant hover:text-primary cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-lg">close</span>
                    </button>
                  </div>

                  <div className="space-y-2 text-xs font-mono">
                    <div className="bg-surface-container-low p-2.5 rounded-xl flex justify-between">
                      <span className="text-on-surface-variant">Event:</span>
                      <span className="font-bold text-primary">{selectedEntryDetails.event_type}</span>
                    </div>
                    <div className="bg-surface-container-low p-2.5 rounded-xl flex justify-between">
                      <span className="text-on-surface-variant">Actor:</span>
                      <span className="font-bold text-on-surface">{selectedEntryDetails.actor}</span>
                    </div>
                    <div className="bg-surface-container-low p-2.5 rounded-xl flex justify-between">
                      <span className="text-on-surface-variant">Target ID:</span>
                      <span className="font-bold text-on-surface">{selectedEntryDetails.target_id}</span>
                    </div>
                    <div className="bg-surface-container-low p-2.5 rounded-xl flex flex-col gap-1">
                      <span className="text-on-surface-variant">Payload SHA-256:</span>
                      <span className="font-bold text-secondary break-all">{selectedEntryDetails.payload_hash}</span>
                    </div>

                    <div className="flex flex-col gap-1 pt-1">
                      <span className="text-[10px] uppercase font-bold text-on-surface-variant">Raw Payload Details:</span>
                      <pre className="p-3 bg-surface-container rounded-xl text-[11px] overflow-x-auto text-on-surface">
                        {JSON.stringify(selectedEntryDetails.details, null, 2)}
                      </pre>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2 border-t border-outline-variant/20">
                    <button
                      type="button"
                      onClick={() => setSelectedEntryDetails(null)}
                      className="px-4 py-2 rounded-xl neu-button text-xs font-semibold text-on-surface cursor-pointer"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

