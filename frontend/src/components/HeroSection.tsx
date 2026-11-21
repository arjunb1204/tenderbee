"use client";

import React, { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/animations";
import { apiClient, TenderSummary } from "@/lib/api";

export default function HeroSection() {
  const router = useRouter();
  const containerRef = useRef<HTMLElement>(null);
  const headlineRef = useRef<HTMLHeadingElement>(null);
  const subheadRef = useRef<HTMLParagraphElement>(null);
  const formRef = useRef<HTMLDivElement>(null);
  const mockupRef = useRef<HTMLDivElement>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [dropdownResults, setDropdownResults] = useState<TenderSummary[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [heroTenders, setHeroTenders] = useState<TenderSummary[]>([]);
  const [loadingHero, setLoadingHero] = useState(true);

  // Load indexed showcase tenders from the local backend without triggering live web scrapes on mount
  useEffect(() => {
    let isMounted = true;
    apiClient.tenders
      .list()
      .then((res) => {
        if (isMounted) {
          const list = Array.isArray(res) ? res : res.results || [];
          setHeroTenders(list.slice(0, 5));
        }
      })
      .catch((err) => {
        console.warn("Could not fetch showcase tenders:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingHero(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Debounced live search preview as user types
  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setDropdownResults([]);
      setIsDropdownOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await apiClient.tenders.search({ query: trimmed, limit: 5 });
        if (res && Array.isArray(res.results)) {
          setDropdownResults(res.results);
          setIsDropdownOpen(true);
        } else {
          setDropdownResults([]);
        }
      } catch (err) {
        console.warn("Live search query failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsDropdownOpen(false);
    const query = searchQuery.trim();
    if (query) {
      router.push(`/tenders?query=${encodeURIComponent(query)}`);
    } else {
      router.push("/tenders");
    }
  };

  const formatValue = (val?: number | null) => {
    if (!val) return "Value Unspecified";
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)} L`;
    return `₹${val.toLocaleString("en-IN")}`;
  };

  useGSAP(
    () => {
      const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (prefersReduced) return;

      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.fromTo(
        headlineRef.current,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.9 }
      )
        .fromTo(
          subheadRef.current,
          { opacity: 0, y: 20 },
          { opacity: 1, y: 0, duration: 0.7 },
          "-=0.5"
        )
        .fromTo(
          formRef.current,
          { opacity: 0, y: 20 },
          { opacity: 1, y: 0, duration: 0.7 },
          "-=0.4"
        )
        .fromTo(
          mockupRef.current,
          { opacity: 0, y: 40 },
          { opacity: 1, y: 0, duration: 0.9 },
          "-=0.5"
        );
    },
    { scope: containerRef }
  );

  return (
    <section
      ref={containerRef}
      className="bg-wave-pattern pt-16 sm:pt-24 pb-20 sm:pb-32 px-4 sm:px-6 lg:px-8 border-b border-indigo-100 overflow-visible"
      data-purpose="hero-section"
    >
      <div className="max-w-4xl mx-auto text-center">
        {/* Display Headline */}
        <h1
          ref={headlineRef}
          className="font-serif editorial-headline text-4xl sm:text-6xl md:text-[68px] leading-[1.08] text-brand-charcoal font-normal tracking-tight"
        >
          Find the Right Tenders Bid with<br className="hidden sm:inline" />
          Confidence
        </h1>

        {/* Supporting Paragraph */}
        <p
          ref={subheadRef}
          className="mt-6 text-base sm:text-lg md:text-xl text-brand-charcoal/80 max-w-2xl mx-auto leading-relaxed"
        >
          Discover relevant opportunities across GeM, CPPP &amp; State feeds, inspect compliance criteria, and verify your eligibility with zero hallucination.
        </p>

        {/* Pill Action Form Input - Neumorphic Inset & Raised Button */}
        <div ref={formRef} className="mt-8 max-w-xl mx-auto relative z-30">
          <form
            onSubmit={handleSearchSubmit}
            className="neu-flat p-2 sm:p-2.5 rounded-full flex items-center justify-between gap-2 relative bg-surface-container-lowest"
          >
            <div className="relative w-full flex items-center">
              <span className="material-symbols-outlined text-slate-400 pl-4 text-xl shrink-0">
                search
              </span>
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  if (dropdownResults.length > 0) setIsDropdownOpen(true);
                }}
                className="w-full neu-pressed-sm rounded-full py-2.5 pl-3 pr-3 text-sm sm:text-base text-brand-charcoal placeholder-gray-400 outline-none"
                placeholder="Search by tender category, keyword (e.g. Services, Solar), or ID..."
                type="text"
                autoComplete="off"
              />
              {isSearching && (
                <span className="absolute right-4 w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></span>
              )}
            </div>
            <button
              className="flex-shrink-0 inline-flex items-center pl-5 pr-2 py-2 text-xs sm:text-sm font-semibold text-white neu-button-primary rounded-full group cursor-pointer transition-transform hover:scale-[1.02]"
              type="submit"
            >
              <span>Explore Tenders</span>
              <span className="w-7 h-7 ml-2 rounded-full bg-white/20 group-hover:bg-white/30 flex items-center justify-center transition-colors">
                <svg className="w-3.5 h-3.5 text-white stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
          </form>

          {/* Quick Search Categories Chips */}
          <div className="flex items-center justify-center gap-2 mt-3 flex-wrap">
            <span className="text-xs text-brand-charcoal/60 font-medium">Popular:</span>
            {["Services", "Security", "Solar", "Civil Works", "BSPHCL"].map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => {
                  setSearchQuery(chip);
                  router.push(`/tenders?query=${encodeURIComponent(chip)}`);
                }}
                className="text-xs px-3 py-1 rounded-full neu-flat-sm text-brand-charcoal/80 hover:text-primary hover:neu-pressed-sm transition-all cursor-pointer font-medium"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Live Search Autocomplete / Instant Results Dropdown */}
          {isDropdownOpen && dropdownResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-2 neu-flat rounded-2xl bg-surface-container-lowest p-3 border border-secondary/20 shadow-2xl z-50 text-left max-h-[380px] overflow-y-auto">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200/80 px-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Live API Matches ({dropdownResults.length})
                </span>
                <button
                  type="button"
                  onClick={() => setIsDropdownOpen(false)}
                  className="text-xs text-slate-400 hover:text-slate-700 cursor-pointer"
                >
                  ✕ Close
                </button>
              </div>

              <div className="flex flex-col gap-2">
                {dropdownResults.map((t) => (
                  <Link
                    key={t.tender_id || t.tender_number}
                    href={`/tenders?query=${encodeURIComponent(searchQuery)}&tender_id=${encodeURIComponent(t.tender_id || t.tender_number)}`}
                    onClick={() => setIsDropdownOpen(false)}
                    className="p-3 rounded-xl neu-flat-sm hover:neu-pressed transition-all flex items-start justify-between gap-3 group bg-white"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-[10px] font-mono font-bold text-primary px-2 py-0.5 rounded neu-pressed-sm">
                          {t.tender_number || t.tender_id}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-semibold">
                          {t.portal || "Live Feed"}
                        </span>
                        {t.state && (
                          <span className="text-[10px] text-slate-500 font-medium">
                            {t.state}
                          </span>
                        )}
                      </div>
                      <h4 className="text-xs sm:text-sm font-semibold text-slate-900 line-clamp-1 group-hover:text-primary transition-colors">
                        {t.title}
                      </h4>
                      <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                        {t.buyer_name}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs sm:text-sm font-bold text-emerald-700 block">
                        {formatValue(t.estimated_value_inr)}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {t.submission_deadline ? `Due ${new Date(t.submission_deadline).toLocaleDateString()}` : "Active"}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>

              {/* View all link */}
              <div className="mt-2 pt-2 border-t border-slate-100 text-center">
                <Link
                  href={`/tenders?query=${encodeURIComponent(searchQuery)}`}
                  onClick={() => setIsDropdownOpen(false)}
                  className="text-xs font-bold text-primary hover:underline inline-flex items-center gap-1"
                >
                  <span>Explore all results in procurement workspace</span>
                  <span>&rarr;</span>
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Hero Dashboard Visual Mockup */}
        <div ref={mockupRef} className="mt-12 sm:mt-16 max-w-3xl mx-auto relative z-10">
          <div className="neu-flat bg-gradient-to-br from-surface-container-low to-surface-container p-3 sm:p-5 rounded-3xl border border-white/80">
            {/* Top Window Controls */}
            <div className="flex items-center justify-between mb-4 px-2">
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full neu-pressed-sm bg-rose-400/80"></span>
                <span className="w-3 h-3 rounded-full neu-pressed-sm bg-amber-400/80"></span>
                <span className="w-3 h-3 rounded-full neu-pressed-sm bg-emerald-400/80"></span>
              </div>
              <div className="text-[11px] font-semibold text-slate-500 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Live Portal Feed &bull; 0 Hallucination Index</span>
              </div>
            </div>

            {/* Tender Mockup Center Card Stack */}
            <div className="neu-pressed rounded-2xl p-6 sm:p-8 flex flex-col items-center justify-center min-h-[260px] sm:min-h-[310px] relative">
              {/* Source Integration Badges */}
              <div className="flex items-center justify-center gap-2 mb-4 flex-wrap">
                <div className="neu-flat-sm rounded-xl px-3 py-1.5 text-xs font-semibold flex items-center gap-2 text-gray-700 bg-surface-container-lowest">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span>GeM Portal</span>
                </div>
                <div className="neu-flat-sm rounded-xl px-3 py-1.5 text-xs font-semibold flex items-center gap-2 text-gray-700 bg-surface-container-lowest">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span>CPPP National</span>
                </div>
                <div className="neu-flat-sm rounded-xl px-3 py-1.5 text-xs font-semibold flex items-center gap-2 text-gray-700 bg-surface-container-lowest">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span>Bihar eProc2</span>
                </div>
                <div className="neu-flat-sm rounded-xl px-3 py-1.5 text-xs font-semibold flex items-center gap-2 text-gray-700 bg-surface-container-lowest">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  <span>IREPS Railways</span>
                </div>
              </div>

              {/* Foreground Live Tender Cards from Backend API */}
              {loadingHero ? (
                <div className="w-full max-w-md neu-flat rounded-2xl p-6 bg-white flex flex-col items-center justify-center gap-2">
                  <span className="w-5 h-5 rounded-full border-2 border-primary border-t-transparent animate-spin"></span>
                  <span className="text-xs text-slate-500 font-medium">Fetching live tenders from procurement engine...</span>
                </div>
              ) : heroTenders.length > 0 ? (
                <div className="w-full max-w-lg flex flex-col gap-3">
                  {heroTenders.slice(0, 2).map((tender) => (
                    <Link
                      key={tender.tender_id || tender.tender_number}
                      href={`/tenders?tender_id=${encodeURIComponent(tender.tender_id || tender.tender_number)}`}
                      className="w-full neu-flat rounded-2xl p-4 transform hover:-translate-y-1 transition-transform text-left cursor-pointer group block bg-white"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 rounded-xl neu-flat-sm bg-purple-50 flex items-center justify-center text-brand-purple group-hover:bg-brand-purple group-hover:text-white transition-colors shrink-0">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                            </svg>
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className="text-[10px] font-mono font-bold text-primary px-2 py-0.5 rounded neu-pressed-sm bg-white">
                                {tender.tender_number}
                              </span>
                              <span className="text-[10px] text-slate-500 font-medium">
                                {tender.portal || "Portal"}
                              </span>
                            </div>
                            <h4 className="text-xs sm:text-sm font-bold text-gray-900 leading-tight line-clamp-1 group-hover:text-primary transition-colors">
                              {tender.title}
                            </h4>
                            <p className="text-[11px] text-gray-500 line-clamp-1 mt-0.5">
                              {tender.buyer_name} {tender.dealing_officer ? `• Officer: ${tender.dealing_officer}` : ""}
                            </p>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold neu-flat-sm bg-emerald-100 text-emerald-800 block">
                            {formatValue(tender.estimated_value_inr)}
                          </span>
                          {tender.emd_amount_inr && (
                            <span className="text-[10px] font-semibold text-slate-600 block mt-0.5">
                              EMD: {formatValue(tender.emd_amount_inr)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Quick Progress & Checklist Line */}
                      <div className="mt-3 pt-2.5 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-600">
                        <span className="flex items-center gap-1.5 min-w-0">
                          <svg className="w-3.5 h-3.5 text-emerald-600 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path clipRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" fillRule="evenodd" />
                          </svg>
                          <span className="truncate">{tender.state || "National"} &bull; {tender.mandatory_documents?.length ? `${tender.mandatory_documents.length} Docs Required` : "Criteria Verified"}</span>
                        </span>
                        <span className="font-medium text-amber-600 neu-pressed-sm px-2 py-0.5 rounded-md text-[10px] shrink-0">
                          {tender.submission_deadline
                            ? `Due ${new Date(tender.submission_deadline).toLocaleDateString()}`
                            : "Intake Ready"}
                        </span>
                      </div>
                    </Link>
                  ))}

                  <div className="text-center pt-1">
                    <Link
                      href="/tenders"
                      className="text-xs font-bold text-primary hover:underline inline-flex items-center gap-1"
                    >
                      <span>Explore all {heroTenders.length} active tenders in discovery engine</span>
                      <span>&rarr;</span>
                    </Link>
                  </div>
                </div>
              ) : (
                /* Fallback if no tenders ingested */
                <Link
                  href="/tenders"
                  className="w-full max-w-md neu-flat rounded-2xl p-4 transform hover:-translate-y-1 transition-transform text-left cursor-pointer group block bg-white"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl neu-flat-sm bg-purple-50 flex items-center justify-center text-brand-purple group-hover:bg-brand-purple group-hover:text-white transition-colors">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="text-xs sm:text-sm font-bold text-gray-900 leading-tight">Explore Live Procurement Tenders</h4>
                        <p className="text-[11px] text-gray-500">GeM &bull; CPPP &bull; State Portals</p>
                      </div>
                    </div>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold neu-flat-sm bg-emerald-100 text-emerald-800">
                      Discovery Ready
                    </span>
                  </div>
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
