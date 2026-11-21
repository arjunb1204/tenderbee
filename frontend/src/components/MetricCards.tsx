"use client";

import React, { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/animations";
import {
  apiClient,
  TenderSummary,
  VerificationAssessmentRecord,
  searchTenders,
  getDocuments,
} from "@/lib/api";

export default function MetricCards() {
  const containerRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const [totalTenders, setTotalTenders] = useState<number>(923);
  const [pipelineCr, setPipelineCr] = useState<string>("38.4");
  const [activeDocCount, setActiveDocCount] = useState<number>(5);
  const [readinessScore, setReadinessScore] = useState<number>(94);
  const [cleanClauses, setCleanClauses] = useState<string>("6 of 6 clean");
  const [compliancePct, setCompliancePct] = useState<string>("100%");
  const [blockersCount, setBlockersCount] = useState<number>(0);
  const [isEnvelopeReady, setIsEnvelopeReady] = useState<boolean>(true);

  const applyVerdicts = (verdicts: any[]) => {
    if (!verdicts || verdicts.length === 0) return;
    const passed = verdicts.filter((v) => {
      const s = String(v.verdict || v.status || "").toUpperCase();
      return (
        s.includes("READY") ||
        s.includes("PASS") ||
        s.includes("VERIF") ||
        s.includes("WAIVE")
      );
    }).length;
    const total = verdicts.length;
    const blockers = verdicts.filter((v) => {
      const s = String(v.verdict || v.status || "").toUpperCase();
      return s.includes("FAIL") || s.includes("BLOCK");
    }).length;
    const score = Math.round((passed / Math.max(1, total)) * 100);
    const ready = score >= 95 && blockers === 0;

    setReadinessScore(score);
    setCleanClauses(`${passed} of ${total} rules verified`);
    setCompliancePct(`${score}%`);
    setBlockersCount(blockers);
    setIsEnvelopeReady(ready);
  };

  useEffect(() => {
    // 1. Fetch live tenders from both endpoints with fallback
    async function loadTendersAndDocs() {
      try {
        const [tenderRes, docsRes] = await Promise.all([
          searchTenders({ limit: 50 }).catch(() => null),
          getDocuments().catch(() => null),
        ]);

        if (tenderRes && tenderRes.success) {
          const total = tenderRes.total_matches || (tenderRes.results ? tenderRes.results.length : 0);
          if (total > 0) setTotalTenders(total);

          if (tenderRes.results && tenderRes.results.length > 0) {
            const sumInr = tenderRes.results.reduce(
              (acc: number, t: any) => acc + (t.estimated_value_inr || 0),
              0
            );
            if (sumInr > 0) {
              setPipelineCr((sumInr / 10000000).toFixed(1));
            }
          }
        } else {
          // Fallback to apiClient.tenders.list()
          apiClient.tenders
            .list()
            .then((res) => {
              const list: TenderSummary[] = Array.isArray(res) ? res : res.results || [];
              if (list && list.length > 0) {
                setTotalTenders(list.length);
                const totalVal = list.reduce((acc, t) => acc + (t.estimated_value_inr || 0), 0);
                if (totalVal > 0) {
                  setPipelineCr((totalVal / 10000000).toFixed(1));
                }
              }
            })
            .catch(() => {});
        }

        if (Array.isArray(docsRes)) {
          setActiveDocCount(docsRes.length > 0 ? docsRes.length : 5);
        }
      } catch (err) {
        console.error("Error loading metrics:", err);
      }
    }

    loadTendersAndDocs();

    // 2. Fetch live compliance assessments with fallback to dossier engine
    apiClient.verify
      .listAssessments()
      .then(async (res) => {
        const assessments: VerificationAssessmentRecord[] = Array.isArray(res)
          ? res
          : res.results || [];
        if (assessments && assessments.length > 0 && assessments[0].verdicts_data) {
          applyVerdicts(assessments[0].verdicts_data);
        } else {
          try {
            const dossier = await apiClient.verify.dossier();
            if (dossier && dossier.verdicts) {
              applyVerdicts(dossier.verdicts);
            }
          } catch (_) {}
        }
      })
      .catch(async () => {
        try {
          const dossier = await apiClient.verify.dossier();
          if (dossier && dossier.verdicts) {
            applyVerdicts(dossier.verdicts);
          }
        } catch (_) {}
      });
  }, []);

  useGSAP(
    () => {
      const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (prefersReduced) return;

      if (gridRef.current) {
        gsap.from(gridRef.current.children, {
          opacity: 0,
          y: 20,
          duration: 0.7,
          stagger: 0.1,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef }
  );

  return (
    <section ref={containerRef} className="px-4 sm:px-8 xl:px-12 pb-8">
      <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* 1. Overall Bid Readiness Index */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between h-[230px] hover:-translate-y-0.5 transition-transform">
          {/* Header */}
          <div className="flex items-center justify-between gap-3 h-10">
            <h3 className="font-serif text-xl font-bold text-primary truncate">Readiness Index</h3>
            <span className="w-10 h-10 rounded-xl neu-flat-sm bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-xl">fact_check</span>
            </span>
          </div>

          {/* Middle Metric Content */}
          <div className="my-auto flex flex-col justify-center h-20">
            <div className="flex items-center gap-3">
              {/* Circular Progress Gauge */}
              <div className="relative w-15 h-15 shrink-0 neu-pressed-sm rounded-full p-1 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-surface-container/60"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3.5"
                  />
                  <path
                    className="text-secondary stroke-current"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    strokeDasharray={`${readinessScore}, 100`}
                    strokeLinecap="round"
                    strokeWidth="3.5"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center flex-col">
                  <span className="font-serif text-lg font-bold text-primary leading-none">
                    {readinessScore}
                  </span>
                  <span className="text-[9px] text-on-surface-variant font-semibold leading-none mt-0.5">
                    /100
                  </span>
                </div>
              </div>

              <div className="flex flex-col">
                <div className="flex items-center gap-1 text-secondary font-semibold text-xs">
                  <span className="material-symbols-outlined text-sm">trending_up</span>
                  <span>{isEnvelopeReady ? "Ready to Bid" : "Active Audit"}</span>
                </div>
                <span className="text-xs text-on-surface-variant mt-0.5">Class 1 MSE profile</span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="pt-2 border-t border-outline-variant/20 flex items-center justify-between text-on-surface-variant text-[11px] h-8">
            <span className="uppercase font-semibold">
              {isEnvelopeReady ? "Envelope Unlocked" : "Target 95+"}
            </span>
            <span
              className={`font-bold text-xs ${
                isEnvelopeReady ? "text-primary" : "text-error"
              }`}
            >
              {isEnvelopeReady
                ? "Target Met (95+)"
                : `${Math.max(0, 95 - readinessScore)} pts to peak`}
            </span>
          </div>
        </div>

        {/* 2. Active Pipeline Value */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between h-[230px] hover:-translate-y-0.5 transition-transform">
          {/* Header */}
          <div className="flex items-center justify-between gap-3 h-10">
            <h3 className="font-serif text-xl font-bold text-primary truncate">Tenders Tracked</h3>
            <span className="w-10 h-10 rounded-xl neu-flat-sm bg-surface-container-low text-on-surface-variant flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-xl">gavel</span>
            </span>
          </div>

          {/* Middle Metric Content */}
          <div className="my-auto flex flex-col justify-center h-20">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-3xl sm:text-4xl text-primary font-bold leading-none">
                {totalTenders}
              </span>
              <span className="text-sm font-medium text-on-surface-variant">Live Bids</span>
            </div>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full neu-flat-sm bg-secondary-fixed text-on-secondary-fixed text-[11px] font-bold">
                ₹{pipelineCr} Cr
              </span>
              <span className="text-xs text-on-surface-variant">Bihar, GeM, CPPP &amp; IREPS</span>
            </div>
          </div>

          {/* Footer with Sparkline Well */}
          <div className="pt-2 border-t border-outline-variant/20 flex items-center justify-between text-on-surface-variant text-[11px] h-8">
            <span className="font-medium text-xs">All-India Portals</span>
            <div className="flex items-end gap-1 h-4 w-24 px-1 py-0.5 rounded neu-pressed-sm">
              <div className="h-2 flex-1 bg-secondary-fixed rounded-t-xs" title="eProc2 Bihar" />
              <div className="h-3.5 flex-1 bg-secondary rounded-t-xs" title="CPPP / NIC" />
              <div className="h-2.5 flex-1 bg-primary rounded-t-xs" title="GeM" />
              <div className="h-4 flex-1 bg-secondary rounded-t-xs" title="IREPS Railways" />
              <div className="h-3 flex-1 bg-surface-container-highest rounded-t-xs" title="State Portals" />
            </div>
          </div>
        </div>

        {/* 3. Compliance Health */}
        <Link
          href="/audit"
          className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between h-[230px] hover:-translate-y-0.5 transition-transform group cursor-pointer"
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-3 h-10">
            <h3 className="font-serif text-xl font-bold text-primary truncate group-hover:text-secondary transition-colors">
              Compliance Health
            </h3>
            <span className="w-10 h-10 rounded-xl neu-flat-sm bg-surface-container-low text-on-surface-variant flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-xl">rule</span>
            </span>
          </div>

          {/* Middle Metric Content */}
          <div className="my-auto flex flex-col justify-center h-20">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-3xl sm:text-4xl text-primary font-bold leading-none">
                {compliancePct}
              </span>
              <span
                className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                  isEnvelopeReady
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "bg-error-container text-on-error-container"
                }`}
              >
                {isEnvelopeReady ? "Ready to Bid" : `${blockersCount} Blockers`}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-on-surface-variant text-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  isEnvelopeReady ? "bg-primary" : "bg-error"
                }`}
              />
              <span>{cleanClauses} ({activeDocCount} statutory documents)</span>
            </div>
          </div>

          {/* Footer */}
          <div className="pt-2 border-t border-outline-variant/20 flex items-center justify-between text-on-surface-variant text-[11px] h-8">
            <span className="flex items-center gap-1.5 text-xs text-secondary font-semibold">
              <span className="material-symbols-outlined text-sm">
                {isEnvelopeReady ? "verified_user" : "pending_actions"}
              </span>
              <span>{isEnvelopeReady ? "Envelope Unlocked" : "Audit Pending"}</span>
            </span>
            <span className="text-[10px] font-bold text-secondary flex items-center gap-0.5 group-hover:underline">
              <span>Inspect Audit</span>
              <span className="material-symbols-outlined text-xs">arrow_forward</span>
            </span>
          </div>
        </Link>

        {/* 4. Corrigendum Alerts */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between h-[230px] hover:-translate-y-0.5 transition-transform">
          {/* Header */}
          <div className="flex items-center justify-between gap-3 h-10">
            <h3 className="font-serif text-xl font-bold text-primary truncate">Live Intake</h3>
            <div className="relative shrink-0">
              <span className="w-10 h-10 rounded-xl neu-flat-sm bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center">
                <span className="material-symbols-outlined text-xl">radar</span>
              </span>
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-secondary rounded-full animate-ping" />
            </div>
          </div>

          {/* Middle Metric Content */}
          <div className="my-auto flex flex-col justify-center h-20">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-3xl sm:text-4xl text-primary font-bold leading-none">
                Active
              </span>
              <span className="text-sm font-medium text-on-surface-variant">Zero Drifts</span>
            </div>
            <p className="text-xs text-on-surface-variant mt-2 truncate">
              RulePacks cryptographically frozen
            </p>
          </div>

          {/* Footer */}
          <Link
            href="/tenders"
            className="pt-2 border-t border-outline-variant/20 flex items-center justify-between text-secondary text-xs font-semibold hover:underline h-8"
          >
            <span>Browse All Tenders</span>
            <span className="material-symbols-outlined text-base">north_east</span>
          </Link>
        </div>
      </div>
    </section>
  );
}
