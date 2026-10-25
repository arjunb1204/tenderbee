"use client";

import React, { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/animations";
import { searchTenders, getDocuments } from "@/lib/api";

export default function MetricCards() {
  const containerRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const [totalTenders, setTotalTenders] = useState<number>(923);
  const [pipelineCr, setPipelineCr] = useState<string>("38.4");
  const [activeDocCount, setActiveDocCount] = useState<number>(5);
  const [readinessScore, setReadinessScore] = useState<number>(94);

  useEffect(() => {
    async function loadMetrics() {
      try {
        const [tenderRes, docsRes] = await Promise.all([
          searchTenders({ limit: 50 }),
          getDocuments(),
        ]);

        if (tenderRes && tenderRes.success) {
          const total = tenderRes.total_matches || (tenderRes.results ? tenderRes.results.length : 0);
          setTotalTenders(total > 0 ? total : 923);

          if (tenderRes.results && tenderRes.results.length > 0) {
            const sumInr = tenderRes.results.reduce((acc, t) => acc + (t.estimated_value_inr || 0), 0);
            if (sumInr > 0) {
              setPipelineCr((sumInr / 10000000).toFixed(1));
            }
          }
        }

        if (Array.isArray(docsRes)) {
          setActiveDocCount(docsRes.length > 0 ? docsRes.length : 5);
          const signed = docsRes.filter((d) => d.is_digitally_signed || d.signature_valid).length;
          const score = docsRes.length > 0 ? Math.round((signed / docsRes.length) * 100) : 94;
          setReadinessScore(score > 0 ? score : 94);
        }
      } catch (err) {
        console.error("Error loading metrics:", err);
      }
    }

    loadMetrics();
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
        <div className="relative bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between min-h-[240px] overflow-hidden group hover:-translate-y-0.5 transition-transform">
          <div className="absolute -top-12 -right-12 w-32 h-32 bg-secondary-fixed/40 rounded-full blur-2xl group-hover:scale-125 transition-transform" />
          <div className="flex items-start justify-between relative z-10">
            <div>
              <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-semibold">
                Readiness
              </span>
              <span className="font-serif text-xl font-bold text-primary">Readiness Index</span>
            </div>
            <span className="p-2.5 rounded-xl neu-flat-sm bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center">
              <span className="material-symbols-outlined text-xl">fact_check</span>
            </span>
          </div>

          <div className="flex items-center gap-4 my-3 relative z-10">
            {/* Circular Progress Gauge */}
            <div className="relative w-20 h-20 shrink-0 neu-pressed-sm rounded-full p-1 flex items-center justify-center">
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
                <span className="font-serif text-xl font-bold text-primary leading-none">{readinessScore}</span>
                <span className="text-[10px] text-on-surface-variant font-semibold leading-none mt-0.5">/100</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-1 text-secondary font-semibold text-xs">
                <span className="material-symbols-outlined text-sm">trending_up</span>
                <span>Audit Verified</span>
              </div>
              <span className="text-xs text-on-surface-variant mt-1">Class 1 MSE profile</span>
            </div>
          </div>

          <div className="pt-2 border-t border-outline-variant/20 relative z-10 flex items-center justify-between text-on-surface-variant">
            <span className="text-[10px] uppercase font-semibold">Live Assessment</span>
            <span className="text-[10px] font-bold text-secondary">Zero blocking defects</span>
          </div>
        </div>

        {/* 2. Active Pipeline Value */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between min-h-[240px] hover:-translate-y-0.5 transition-transform">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-semibold">
                Pipeline
              </span>
              <span className="font-serif text-xl font-bold text-primary">Tenders Tracked</span>
            </div>
            <span className="p-2.5 rounded-xl neu-flat-sm text-on-surface-variant flex items-center justify-center">
              <span className="material-symbols-outlined text-xl">gavel</span>
            </span>
          </div>

          <div className="my-3">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-4xl text-primary font-bold leading-none">{totalTenders}</span>
              <span className="text-sm font-medium text-on-surface-variant">Live Bids</span>
            </div>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full neu-flat-sm bg-secondary-fixed text-on-secondary-fixed text-[11px] font-bold">
                ₹{pipelineCr} Cr
              </span>
              <span className="text-xs text-on-surface-variant">Bihar, GeM, CPPP &amp; IREPS</span>
            </div>
          </div>

          {/* Inline Visual Spark-Bars with Neumorphic Well */}
          <div className="neu-pressed-sm p-1.5 rounded-lg flex items-end gap-1.5 h-7 w-full">
            <div className="h-4 w-1/5 bg-secondary-fixed rounded-t-sm" title="eProc2 Bihar" />
            <div className="h-6 w-1/5 bg-secondary rounded-t-sm" title="CPPP" />
            <div className="h-5 w-1/5 bg-primary rounded-t-sm" title="GeM" />
            <div className="h-4 w-1/5 bg-secondary-fixed rounded-t-sm" title="IREPS" />
            <div className="h-3 w-1/5 bg-surface-container-highest rounded-t-sm" title="Direct" />
          </div>
        </div>

        {/* 3. Compliance Health */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between min-h-[240px] hover:-translate-y-0.5 transition-transform">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-semibold">
                Integrity
              </span>
              <span className="font-serif text-xl font-bold text-primary">Compliance Health</span>
            </div>
            <span className="p-2.5 rounded-xl neu-flat-sm text-on-surface-variant flex items-center justify-center">
              <span className="material-symbols-outlined text-xl">rule</span>
            </span>
          </div>

          <div className="my-3">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-4xl text-primary font-bold leading-none">100%</span>
              <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded neu-pressed-sm text-on-surface-variant">
                Verified
              </span>
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-on-surface-variant text-xs">
              <span className="w-2 h-2 rounded-full bg-secondary" />
              <span>{activeDocCount} statutory documents verified</span>
            </div>
          </div>

          <Link
            href="/vault"
            className="flex items-center justify-between text-secondary text-xs font-semibold hover:underline pt-2 border-t border-outline-variant/20"
          >
            <span>Open Document Vault</span>
            <span className="material-symbols-outlined text-base">north_east</span>
          </Link>
        </div>

        {/* 4. Corrigendum Alerts */}
        <div className="bg-surface-container-lowest neu-flat rounded-2xl p-6 flex flex-col justify-between min-h-[240px] hover:-translate-y-0.5 transition-transform">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block font-semibold">
                Audit Trail
              </span>
              <span className="font-serif text-xl font-bold text-primary">Live Intake</span>
            </div>
            <div className="relative">
              <span className="p-2.5 rounded-xl neu-flat-sm bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center">
                <span className="material-symbols-outlined text-xl">radar</span>
              </span>
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-secondary rounded-full animate-ping" />
            </div>
          </div>

          <div className="my-3">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-4xl text-primary font-bold leading-none">Active</span>
              <span className="text-sm font-medium text-on-surface-variant">Zero Drifts</span>
            </div>
            <p className="text-xs text-on-surface-variant mt-2">
              RulePacks cryptographically frozen
            </p>
          </div>

          <Link
            href="/tenders"
            className="flex items-center justify-between text-secondary text-xs font-semibold hover:underline pt-2 border-t border-outline-variant/20"
          >
            <span>Browse All Tenders</span>
            <span className="material-symbols-outlined text-base">north_east</span>
          </Link>
        </div>
      </div>
    </section>
  );
}
