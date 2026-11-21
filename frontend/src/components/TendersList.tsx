"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { searchTenders, apiClient, TenderItem, TenderSummary } from "@/lib/api";
import { formatINR } from "@/lib/utils";

export default function TendersList() {
  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await searchTenders({ limit: 4 });
        if (res.success && res.results && res.results.length > 0) {
          setTenders(res.results);
        } else {
          // Fallback to apiClient.tenders.list()
          const listRes = await apiClient.tenders.list();
          const items: TenderSummary[] = Array.isArray(listRes) ? listRes : listRes.results || [];
          if (items.length > 0) {
            setTenders(
              items.map((t) => ({
                tender_id: t.tender_id,
                tender_number: t.tender_number || t.tender_id,
                title: t.title,
                buyer_name: t.buyer_name,
                portal: t.portal,
                state: t.state,
                category: t.category,
                estimated_value_inr: t.estimated_value_inr ?? undefined,
                emd_amount_inr: t.emd_amount_inr ?? undefined,
                submission_deadline: t.submission_deadline ?? undefined,
                status: t.status,
              })) as TenderItem[]
            );
          }
        }
      } catch (e) {
        console.error("Dashboard TendersList load error:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-widest block font-semibold">
            Live Procurement Index
          </span>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-primary">
            Active Tenders &amp; Tracked Bids
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/tenders"
            className="px-3.5 py-1.5 rounded-full neu-button-primary text-xs font-semibold flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm">search</span>
            <span>Search &amp; Intake Tenders</span>
          </Link>
        </div>
      </div>

      {loading && (
        <div className="p-8 bg-surface-container-lowest neu-flat rounded-2xl flex items-center justify-center gap-3">
          <div className="w-6 h-6 border-2 border-secondary border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-on-surface-variant font-medium">Loading live tenders...</span>
        </div>
      )}

      {!loading && tenders.length === 0 && (
        <div className="p-8 text-center bg-surface-container-lowest neu-flat rounded-2xl text-xs text-on-surface-variant">
          No live tenders indexed yet. Click &quot;Search &amp; Intake Tenders&quot; to discover opportunities.
        </div>
      )}

      {/* Tender Cards */}
      {!loading &&
        tenders.map((tender) => {
          const val = tender.estimated_value_inr;
          const valStr = val ? formatINR(val) : "Not Specified";
          const emd = tender.emd_amount_inr;
          const emdStr = emd ? formatINR(emd) : "Exempt / Nil";
          const portal = tender.portal || "Government Portal";

          return (
            <div
              key={tender.tender_id || tender.tender_number}
              className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col gap-4 hover:-translate-y-0.5 transition-transform"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="w-12 h-12 rounded-xl neu-flat-sm bg-primary-container text-on-primary flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined text-2xl">
                      {portal.includes("railway") || portal.includes("ireps")
                        ? "train"
                        : portal.includes("hry") || portal.includes("cppp")
                        ? "local_hospital"
                        : "corporate_fare"}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] px-2 py-0.5 rounded-full neu-pressed-sm text-on-surface-variant font-mono font-medium">
                        {tender.tender_number}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full neu-flat-sm font-bold ${
                          portal.includes("eproc2.bihar")
                            ? "bg-emerald-100 text-emerald-900"
                            : portal.includes("gem")
                            ? "bg-secondary-fixed text-on-secondary-fixed"
                            : portal.includes("ireps")
                            ? "bg-amber-100 text-amber-900"
                            : "bg-blue-100 text-blue-900"
                        }`}
                      >
                        {portal}
                      </span>
                      <span className="text-[10px] text-on-surface-variant flex items-center gap-1 font-medium">
                        <span className="material-symbols-outlined text-sm">schedule</span>
                        {tender.submission_deadline
                          ? tender.submission_deadline.split("T")[0]
                          : "Active Notice"}
                      </span>
                    </div>
                    <h3 className="font-serif text-lg sm:text-xl text-primary mt-1 font-bold">
                      {tender.title}
                    </h3>
                    <p className="text-xs text-on-surface-variant">
                      {tender.buyer_name} • {tender.state || "All India"}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col md:items-end shrink-0">
                  <span className="font-serif text-2xl font-bold text-primary">{valStr}</span>
                  <span className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                    Value
                  </span>
                </div>
              </div>

              {/* Compliance Ribbon - Neumorphic Well */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 rounded-xl neu-pressed">
                <div className="flex flex-col">
                  <span className="text-[10px] text-on-surface-variant uppercase font-semibold">
                    Dealing Officer
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs font-bold text-primary truncate">
                      {tender.dealing_officer || "Department Officer"}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-on-surface-variant uppercase font-semibold">
                    EMD Required
                  </span>
                  <span className="text-xs font-semibold text-on-surface mt-0.5 flex items-center gap-1">
                    <span
                      className="material-symbols-outlined text-secondary text-base"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      check_circle
                    </span>
                    {emdStr}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-on-surface-variant uppercase font-semibold">
                    Category
                  </span>
                  <span className="text-xs font-medium text-on-surface mt-0.5 flex items-center gap-1">
                    <span className="material-symbols-outlined text-on-surface-variant text-base">
                      category
                    </span>
                    {tender.category || "Services & Works"}
                  </span>
                </div>
              </div>

              {/* Action Row */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span className="text-xs text-on-surface-variant">
                    Portal Status: <strong className="text-on-surface">Live &amp; Verified</strong>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/tenders?tender_id=${encodeURIComponent(tender.tender_number)}`}
                    className="px-4 py-1.5 rounded-full neu-button text-xs font-semibold text-primary hover:bg-surface-container transition-all cursor-pointer"
                  >
                    View Details
                  </Link>
                  <Link
                    href={`/audit?tender_id=${encodeURIComponent(tender.tender_number)}`}
                    className="px-4 py-1.5 rounded-full neu-button-primary text-xs font-bold text-white bg-primary hover:bg-primary/90 flex items-center gap-1 transition-all"
                  >
                    <span>Audit Verdict</span>
                    <span className="material-symbols-outlined text-base">chevron_right</span>
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
    </div>
  );
}
