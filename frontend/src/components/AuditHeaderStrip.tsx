"use client";

import React, { useState, useEffect } from "react";
import { searchTenders, apiClient, TenderItem, TenderSummary } from "@/lib/api";

interface AuditHeaderStripProps {
  selectedBid?: string;
  onSelectBid?: (id: string, tenderObj?: any) => void;
}

export default function AuditHeaderStrip({
  selectedBid: propSelectedBid,
  onSelectBid,
}: AuditHeaderStripProps = {}) {
  const [tenders, setTenders] = useState<any[]>([]);
  const [selectedBid, setSelectedBid] = useState(propSelectedBid || "");
  const [selectedTenderObj, setSelectedTenderObj] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (propSelectedBid && propSelectedBid !== selectedBid) {
      setSelectedBid(propSelectedBid);
      const found = tenders.find(
        (t) => t.tender_id === propSelectedBid || t.tender_number === propSelectedBid
      );
      if (found) setSelectedTenderObj(found);
    }
  }, [propSelectedBid, tenders]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await searchTenders({ limit: 20 });
        let list: any[] = [];
        if (res.success && res.results && res.results.length > 0) {
          list = res.results;
        } else {
          const apiRes = await apiClient.tenders.list();
          list = Array.isArray(apiRes) ? apiRes : apiRes.results || [];
        }

        if (list.length > 0) {
          setTenders(list);
          const initialBid =
            propSelectedBid || list[0].tender_number || list[0].tender_id;
          const matched =
            list.find(
              (t) => t.tender_number === initialBid || t.tender_id === initialBid
            ) || list[0];
          const matchedKey = matched.tender_number || matched.tender_id;
          setSelectedBid(matchedKey);
          setSelectedTenderObj(matched);
          if (onSelectBid && !propSelectedBid) {
            onSelectBid(matchedKey, matched);
          }
        }
      } catch (err) {
        console.error("Failed to load audit tenders:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSelectBid = (id: string) => {
    setSelectedBid(id);
    const found =
      tenders.find((t) => t.tender_number === id || t.tender_id === id) || null;
    if (found) setSelectedTenderObj(found);
    if (onSelectBid) {
      onSelectBid(id, found);
    }
  };

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
            Portal: {selectedTenderObj?.portal || "eProc / GeM"}
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
              value={selectedBid}
              onChange={(e) => handleSelectBid(e.target.value)}
              className="appearance-none bg-surface-container-low text-on-surface font-serif text-lg sm:text-xl font-bold pl-4 pr-10 py-2 rounded-xl cursor-pointer focus:outline-none focus:bg-surface-container focus:ring-2 focus:ring-primary/20 border border-outline-variant/30 transition-all w-full sm:w-auto max-w-xl truncate"
            >
              {loading && <option>Loading live tenders from backend...</option>}
              {!loading && tenders.length > 0
                ? tenders.map((t, idx) => {
                    const keyVal = t.tender_number || t.tender_id || `tender-${idx}`;
                    return (
                      <option key={keyVal} value={keyVal}>
                        {t.title} · [{t.tender_number || t.tender_id}]
                      </option>
                    );
                  })
                : [
                    <option key="gem-992140" value="gem-992140">
                      CPWD Integrated Facility Management · GEM/2025/B/992140
                    </option>,
                    <option key="cppp-883102" value="cppp-883102">
                      MES Command Hospital HVAC Retrofit · GEM/2025/B/883102
                    </option>,
                  ]}
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
            <span>
              Nodal Authority:{" "}
              {selectedTenderObj?.buyer_name || "Central Public Works Department"}
            </span>
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
            <span className="text-[10px] uppercase font-bold text-on-surface-variant">
              Deadline
            </span>
            <span className="text-xs font-bold text-error leading-tight">
              {selectedTenderObj?.submission_deadline
                ? new Date(selectedTenderObj.submission_deadline).toLocaleDateString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                  })
                : "Active Closing"}
            </span>
          </div>
        </div>

        {/* EMD Status */}
        <div className="flex-1 sm:flex-initial bg-surface-container-low px-4 py-2.5 rounded-xl flex items-center gap-3 border border-outline-variant/20">
          <div className="w-10 h-10 rounded-full bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center shrink-0">
            <span
              className="material-symbols-outlined text-xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              verified
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-on-surface-variant">
              EMD Status
            </span>
            <span className="text-xs font-bold text-on-surface leading-tight">
              {selectedTenderObj?.emd_amount_inr
                ? `₹${(selectedTenderObj.emd_amount_inr / 100000).toFixed(1)} Lakh (MSE Exempt)`
                : "Exempt · Rule 153 GFR"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
