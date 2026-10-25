"use client";

import React, { useState, useEffect } from "react";
import { searchTenders, TenderItem } from "@/lib/api";

export default function AuditHeaderStrip() {
  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [selectedBidId, setSelectedBidId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await searchTenders({ limit: 20 });
        if (res.success && res.results.length > 0) {
          setTenders(res.results);
          setSelectedBidId(res.results[0].tender_number);
        }
      } catch (err) {
        console.error("Failed to load audit tenders:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const activeTender = tenders.find((t) => t.tender_number === selectedBidId) || tenders[0];

  return (
    <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/30 flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative overflow-hidden">
      <div className="flex flex-col gap-2 max-w-2xl">
        {/* Eyebrow Chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-wider text-secondary font-bold bg-secondary-fixed px-2.5 py-0.5 rounded-full">
            Autonomous Bid Audit
          </span>
          <span className="text-on-surface-variant text-xs">·</span>
          <span className="text-[10px] font-semibold text-on-surface-variant tracking-wider uppercase">
            Portal: {activeTender ? activeTender.portal : "eProc / GeM"}
          </span>
        </div>

        {/* Tender Picker Dropdown */}
        <div className="flex items-center gap-2 mt-1">
          <label className="sr-only" htmlFor="tender-picker">
            Select Bid Subject
          </label>
          <div className="relative inline-flex items-center w-full sm:w-auto">
            <select
              id="tender-picker"
              value={selectedBidId}
              onChange={(e) => setSelectedBidId(e.target.value)}
              className="appearance-none bg-surface-container-low text-on-surface font-serif text-lg sm:text-xl font-bold pl-4 pr-10 py-2 rounded-xl cursor-pointer focus:outline-none focus:bg-surface-container focus:ring-2 focus:ring-primary/20 border border-outline-variant/30 transition-all w-full sm:w-auto max-w-xl truncate"
            >
              {loading && <option>Loading live tenders from backend...</option>}
              {!loading && tenders.map((t) => (
                <option key={t.tender_id || t.tender_number} value={t.tender_number}>
                  {t.title} · [{t.tender_number}]
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-3 pointer-events-none text-on-surface-variant text-xl">
              expand_more
            </span>
          </div>
        </div>

        {/* Company & Authority Line */}
        <div className="flex items-center gap-4 flex-wrap pt-1 text-on-surface-variant text-xs font-medium">
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-base text-primary">domain</span>
            <span>Enterprise Bidder (Default Workspace)</span>
          </div>
          <span>•</span>
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-base text-primary">account_balance</span>
            <span>Nodal Authority: {activeTender ? activeTender.buyer_name : "Central Public Works Department"}</span>
          </div>
        </div>
      </div>

      {/* Action indicators & Milestones */}
      <div className="flex items-stretch sm:items-center gap-3 flex-wrap lg:flex-nowrap">
        {/* Countdown Card */}
        <div className="flex-1 sm:flex-initial bg-surface-container-low px-4 py-2.5 rounded-xl flex items-center gap-3 border border-outline-variant/20">
          <div className="w-10 h-10 rounded-full bg-error-container text-on-error-container flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-xl">hourglass_top</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-on-surface-variant">Deadline</span>
            <span className="text-xs font-bold text-error leading-tight">
              {activeTender?.submission_deadline
                ? new Date(activeTender.submission_deadline).toLocaleDateString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                  })
                : "Active Closing"}
            </span>
          </div>
        </div>

        {/* EMD Exemption Status */}
        <div className="flex-1 sm:flex-initial bg-surface-container-low px-4 py-2.5 rounded-xl flex items-center gap-3 border border-outline-variant/20">
          <div className="w-10 h-10 rounded-full bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              verified
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-on-surface-variant">EMD Exemption</span>
            <span className="text-xs font-bold text-on-surface leading-tight">
              {activeTender?.emd_amount_inr ? `₹${(activeTender.emd_amount_inr / 100000).toFixed(1)} Lakh (MSE Exempt)` : "Exempt · Rule 153 GFR"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
