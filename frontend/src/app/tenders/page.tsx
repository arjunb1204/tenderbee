"use client";

import React, { useState, useEffect, useTransition, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { searchTenders, getTenderDetail, uploadTenderPdf, TenderItem } from "@/lib/api";
import { formatINR } from "@/lib/utils";

function TendersListInner() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPortal, setSelectedPortal] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);
  const [isSearching, startTransition] = useTransition();

  // Selected tender for deep inspection modal
  const [inspectTender, setInspectTender] = useState<TenderItem | null>(null);
  const [inspectLoading, setInspectLoading] = useState<boolean>(false);
  const [inspectTab, setInspectTab] = useState<"skim" | "clauses" | "rulepack" | "json">("skim");

  // PDF Upload modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Fetch initial tenders on load
  const loadTenders = async (q?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await searchTenders({ q, limit: 50 });
      if (res.success && Array.isArray(res.results)) {
        setTenders(res.results);
      } else {
        setTenders([]);
        if (res.error) setError(res.error);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load tenders from backend");
      setTenders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialQuery) {
      setSearchQuery(initialQuery);
      loadTenders(initialQuery);
    } else {
      loadTenders();
    }
  }, [initialQuery]);

  // Handle live search
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(() => {
      loadTenders(searchQuery);
    });
  };

  // Inspect specific tender with eye-button preview
  const handleInspect = async (tenderNumber: string) => {
    setInspectLoading(true);
    setInspectTab("skim");
    try {
      const detailed = await getTenderDetail(tenderNumber, "detailed");
      setInspectTender(detailed || tenders.find((t) => t.tender_number === tenderNumber) || null);
    } catch (err) {
      setInspectTender(tenders.find((t) => t.tender_number === tenderNumber) || null);
    } finally {
      setInspectLoading(false);
    }
  };

  // Handle PDF upload
  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    setIsUploading(true);
    setUploadStatus("Uploading & computing SHA-256 hash...");
    try {
      setUploadStatus("Extracting clauses, financials, and drafting RulePack...");
      const res = await uploadTenderPdf(uploadFile);
      if (res.success && res.tender_id) {
        setUploadStatus("Successfully parsed and indexed!");
        setTimeout(() => {
          setIsUploadModalOpen(false);
          setUploadFile(null);
          setUploadStatus("");
          setIsUploading(false);
          loadTenders();
          if (res.tender_id) handleInspect(res.tender_id);
        }, 1200);
      } else {
        setUploadStatus(`Error: ${res.error || "Failed to process PDF"}`);
        setIsUploading(false);
      }
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message || "Failed to process PDF"}`);
      setIsUploading(false);
    }
  };

  // Filter tenders by portal chip
  const filteredTenders = tenders.filter((t) => {
    if (selectedPortal === "All") return true;
    const portal = (t.portal || "").toLowerCase();
    if (selectedPortal === "GeM") return portal.includes("gem");
    if (selectedPortal === "CPPP") return portal.includes("cppp") || portal.includes("nic.in") || portal.includes("hry");
    if (selectedPortal === "IREPS") return portal.includes("ireps") || portal.includes("railway");
    if (selectedPortal === "Bihar") return portal.includes("eproc2.bihar") || (t.state && t.state.toLowerCase() === "bihar");
    return true;
  });

  // Calculate summary metrics
  const totalVal = filteredTenders.reduce((sum, t) => sum + (t.estimated_value_inr || 0), 0);

  return (
    <div className="bg-surface font-sans text-on-surface antialiased min-h-screen">
      <Sidebar activeTab="tenders" />

      <div className="lg:pl-72 flex flex-col min-h-screen">
        <DashboardHeader />

        <main className="w-full pt-16 bg-surface min-h-screen">
          <div className="px-4 sm:px-8 xl:px-12 py-8 flex flex-col gap-6 max-w-[1500px] mx-auto w-full pb-24">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                    Connected Live: TenderBee Core API
                  </span>
                </div>
                <h1 className="font-serif text-3xl sm:text-4xl font-bold text-primary mt-1">
                  Open Tenders Radar
                </h1>
                <p className="text-sm text-on-surface-variant mt-0.5">
                  Live indexed discovery across GeM, CPPP, IREPS &amp; 28 State Procurement portals.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsUploadModalOpen(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-secondary text-white text-xs font-bold shadow-md hover:bg-secondary/90 transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-base">upload_file</span>
                  <span>Upload Tender PDF</span>
                </button>
                <Link
                  href="/audit"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full neu-button text-xs font-bold text-primary hover:bg-surface-container transition-all"
                >
                  <span className="material-symbols-outlined text-base">verified</span>
                  <span>Run Bid Audit</span>
                </Link>
              </div>
            </div>

            {/* Live Metrics Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-surface-container-lowest neu-flat p-5 rounded-2xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-on-surface-variant">Live Indexed Matches</span>
                  <p className="font-serif text-2xl font-bold text-primary mt-0.5">
                    {loading ? "..." : `${filteredTenders.length} Tenders`}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl neu-flat-sm bg-secondary-fixed flex items-center justify-center text-on-secondary-fixed">
                  <span className="material-symbols-outlined text-xl">gavel</span>
                </div>
              </div>

              <div className="bg-surface-container-lowest neu-flat p-5 rounded-2xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-on-surface-variant">Pipeline Volume</span>
                  <p className="font-serif text-2xl font-bold text-secondary mt-0.5">
                    {loading ? "..." : totalVal > 0 ? formatINR(totalVal) : "₹0.00"}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl neu-flat-sm bg-purple-50 flex items-center justify-center text-brand-purple">
                  <span className="material-symbols-outlined text-xl">account_balance_wallet</span>
                </div>
              </div>

              <div className="bg-surface-container-lowest neu-flat p-5 rounded-2xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-on-surface-variant">Active Portals</span>
                  <p className="font-serif text-2xl font-bold text-emerald-700 mt-0.5">GeM • CPPP • eProc2</p>
                </div>
                <div className="w-10 h-10 rounded-xl neu-flat-sm bg-emerald-50 flex items-center justify-center text-emerald-600">
                  <span className="material-symbols-outlined text-xl">sync_saved_locally</span>
                </div>
              </div>
            </div>

            {/* Filter & Live Search Bar */}
            <div className="bg-surface-container-lowest neu-flat p-4 sm:p-5 rounded-2xl flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
              {/* Portal Selector Tabs */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
                {["All", "Bihar", "CPPP", "GeM", "IREPS"].map((portal) => (
                  <button
                    key={portal}
                    onClick={() => setSelectedPortal(portal)}
                    className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap ${
                      selectedPortal === portal
                        ? "neu-button-primary font-semibold text-white bg-primary"
                        : "neu-button text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    {portal === "Bihar" ? "eProc2 Bihar" : portal}
                  </button>
                ))}
              </div>

              {/* Live search input */}
              <form onSubmit={handleSearch} className="relative flex-1 max-w-lg flex items-center gap-2">
                <div className="relative w-full">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                    search
                  </span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by tender no (141349), keywords, buyer, state..."
                    className="w-full pl-10 pr-4 py-2.5 neu-pressed rounded-xl text-xs sm:text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-secondary/40 transition-all"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || isSearching}
                  className="px-4 py-2.5 rounded-xl bg-primary text-white text-xs font-bold shrink-0 hover:bg-primary/90 transition-all cursor-pointer"
                >
                  {loading || isSearching ? "..." : "Search"}
                </button>
              </form>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-error-container text-on-error-container text-xs flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">error</span>
                <span>{error}</span>
              </div>
            )}

            {/* Loading Skeleton */}
            {loading && (
              <div className="flex flex-col gap-4 py-8 items-center justify-center">
                <div className="w-10 h-10 border-4 border-secondary border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-on-surface-variant font-medium">Querying live backend discovery index...</span>
              </div>
            )}

            {/* Empty State */}
            {!loading && filteredTenders.length === 0 && (
              <div className="p-12 text-center bg-surface-container-lowest neu-flat rounded-2xl flex flex-col items-center justify-center gap-3">
                <span className="material-symbols-outlined text-4xl text-on-surface-variant">search_off</span>
                <h3 className="font-serif text-lg font-bold text-primary">No Matching Tenders Found</h3>
                <p className="text-xs text-on-surface-variant max-w-md">
                  Try adjusting your search criteria, searching for a tender number (e.g. &apos;141349&apos; or &apos;2026_HRY_530295_1&apos;), or uploading a tender PDF.
                </p>
                <button
                  onClick={() => {
                    setSearchQuery("");
                    setSelectedPortal("All");
                    loadTenders("");
                  }}
                  className="mt-2 px-4 py-2 rounded-full neu-button text-xs font-bold text-primary cursor-pointer"
                >
                  Reset All Filters
                </button>
              </div>
            )}

            {/* Live Tenders List */}
            {!loading && (
              <div className="flex flex-col gap-4">
                {filteredTenders.map((tender) => {
                  const val = tender.estimated_value_inr;
                  const valStr = val ? formatINR(val) : "Not Specified";
                  const emd = tender.emd_amount_inr;
                  const emdStr = emd ? formatINR(emd) : "Exempted / Nil";
                  const portal = tender.portal || "Government Portal";

                  return (
                    <div
                      key={tender.tender_id}
                      className="bg-surface-container-lowest neu-flat rounded-2xl p-5 sm:p-6 hover:-translate-y-0.5 transition-all flex flex-col gap-4"
                    >
                      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                        <div className="flex items-start gap-3.5">
                          <div className="w-11 h-11 rounded-xl bg-surface-container-high text-primary flex items-center justify-center shrink-0 shadow-xs">
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
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono font-bold">
                                {tender.tender_number}
                              </span>
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
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
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 font-medium">
                                {tender.category || "Services"} • {tender.state || "All India"}
                              </span>
                            </div>
                            <h3 className="font-serif text-lg sm:text-xl font-bold text-primary mt-1">
                              {tender.title}
                            </h3>
                            <p className="text-xs text-on-surface-variant mt-0.5">
                              {tender.buyer_name}
                            </p>
                          </div>
                        </div>

                        <div className="flex lg:flex-col items-center lg:items-end justify-between lg:justify-center shrink-0 border-t lg:border-t-0 pt-2 lg:pt-0 border-gray-100">
                          <span className="font-serif text-2xl font-bold text-primary">{valStr}</span>
                          <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
                            Estimated Value
                          </span>
                        </div>
                      </div>

                      {/* Badges Ribbon - Neumorphic Inset */}
                      <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 p-3 rounded-xl neu-pressed text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-on-surface-variant text-[11px]">EMD Amount:</span>
                          <span className="font-semibold text-on-surface truncate">{emdStr}</span>
                        </div>
                        <div className="flex items-center justify-between border-t sm:border-t-0 sm:border-l border-white/60 pt-1.5 sm:pt-0 sm:pl-3">
                          <span className="text-on-surface-variant text-[11px]">Tender Fee:</span>
                          <span className="font-semibold text-on-surface truncate">
                            {tender.tender_fee_inr ? `₹${tender.tender_fee_inr.toLocaleString("en-IN")}` : "Exempt / Nil"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between border-t sm:border-t-0 sm:border-l border-white/60 pt-1.5 sm:pt-0 sm:pl-3">
                          <span className="text-on-surface-variant text-[11px]">Dealing Officer:</span>
                          <span className="font-semibold text-on-surface truncate max-w-[150px]">
                            {tender.dealing_officer || "N/A"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between border-t sm:border-t-0 sm:border-l border-white/60 pt-1.5 sm:pt-0 sm:pl-3">
                          <span className="text-on-surface-variant text-[11px]">Deadline:</span>
                          <span className="font-semibold text-secondary truncate">
                            {tender.submission_deadline ? tender.submission_deadline.split("T")[0] : "Active Notice"}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-xs text-on-surface-variant">
                          Status: <strong className="text-emerald-700 font-bold">ACTIVE</strong>
                          {tender.has_pdf_document && (
                            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-900 font-bold">
                              PDF Parsed
                            </span>
                          )}
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleInspect(tender.tender_number)}
                            className="px-4 py-1.5 rounded-full neu-button text-xs font-bold text-primary flex items-center gap-1.5 hover:bg-surface-container transition-all cursor-pointer"
                          >
                            <span className="material-symbols-outlined text-base text-secondary">visibility</span>
                            <span>Eye Button Details</span>
                          </button>
                          <Link
                            href={`/audit?tender_id=${encodeURIComponent(tender.tender_number)}`}
                            className="px-4 py-1.5 rounded-full neu-button-primary text-xs font-bold text-white bg-primary flex items-center gap-1 hover:bg-primary/90 transition-all"
                          >
                            <span>Verify Compliance</span>
                            <span className="material-symbols-outlined text-base">chevron_right</span>
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* ========================================================================= */}
      {/* TENDER DETAILS & EYE BUTTON PREVIEW MODAL */}
      {/* ========================================================================= */}
      {inspectTender && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-container-lowest neu-flat rounded-3xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="p-6 border-b border-gray-200/80 flex items-start justify-between gap-4 bg-surface-container-low">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-bold">
                    {inspectTender.portal || "Government Portal"}
                  </span>
                  <span className="text-xs font-mono font-bold text-primary">
                    {inspectTender.tender_number}
                  </span>
                </div>
                <h2 className="font-serif text-xl sm:text-2xl font-bold text-primary mt-1">
                  {inspectTender.title}
                </h2>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  {inspectTender.buyer_name}
                </p>
              </div>
              <button
                onClick={() => setInspectTender(null)}
                className="w-8 h-8 rounded-full neu-button flex items-center justify-center text-on-surface-variant hover:text-on-surface cursor-pointer shrink-0"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div className="flex items-center gap-2 px-6 pt-3 border-b border-gray-200/80 bg-surface">
              {[
                { id: "skim", label: "Eye Button Preview", icon: "visibility" },
                { id: "clauses", label: "Extracted Clauses", icon: "menu_book" },
                { id: "rulepack", label: "Generated RulePack", icon: "rule" },
                { id: "json", label: "Raw JSON Schema", icon: "code" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setInspectTab(tab.id as any)}
                  className={`px-4 py-2 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                    inspectTab === tab.id
                      ? "border-secondary text-secondary"
                      : "border-transparent text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-5">
              {inspectLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <div className="w-8 h-8 border-3 border-secondary border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs text-on-surface-variant">Acquiring deep clauses and rule pack...</span>
                </div>
              ) : inspectTab === "skim" ? (
                <>
                  {/* Financial & Officer Matrix */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col">
                      <span className="text-[10px] text-on-surface-variant uppercase font-bold">Estimated Value</span>
                      <span className="font-serif text-xl font-bold text-primary mt-1">
                        {inspectTender.estimated_value_inr ? formatINR(inspectTender.estimated_value_inr) : "Not Specified"}
                      </span>
                    </div>

                    <div className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col">
                      <span className="text-[10px] text-on-surface-variant uppercase font-bold">EMD Amount</span>
                      <span className="font-serif text-xl font-bold text-secondary mt-1">
                        {inspectTender.emd_amount_inr ? formatINR(inspectTender.emd_amount_inr) : "Exempted / Nil"}
                      </span>
                    </div>

                    <div className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col">
                      <span className="text-[10px] text-on-surface-variant uppercase font-bold">Tender Fee</span>
                      <span className="font-serif text-xl font-bold text-on-surface mt-1">
                        {inspectTender.tender_fee_inr ? `₹${inspectTender.tender_fee_inr.toLocaleString("en-IN")}` : "Nil"}
                      </span>
                    </div>

                    <div className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col">
                      <span className="text-[10px] text-on-surface-variant uppercase font-bold">Processing Fee</span>
                      <span className="font-serif text-xl font-bold text-on-surface mt-1">
                        {inspectTender.processing_fee_inr ? `₹${inspectTender.processing_fee_inr.toLocaleString("en-IN")}` : "Nil"}
                      </span>
                    </div>
                  </div>

                  {/* Officer & Administrative Details */}
                  <div className="p-5 rounded-2xl bg-surface-container-low neu-flat flex flex-col gap-3">
                    <h3 className="font-serif text-base font-bold text-primary flex items-center gap-2">
                      <span className="material-symbols-outlined text-secondary">person_check</span>
                      <span>Procurement Officer &amp; Authority Details</span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-on-surface-variant font-medium">Dealing Officer:</span>
                        <p className="font-bold text-primary text-sm mt-0.5">
                          {inspectTender.dealing_officer || "Not specified in notice"}
                        </p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-medium">Department Hierarchy:</span>
                        <p className="font-bold text-primary text-sm mt-0.5">
                          {inspectTender.org_hierarchy && inspectTender.org_hierarchy.length > 0
                            ? inspectTender.org_hierarchy.join(" → ")
                            : inspectTender.buyer_name}
                        </p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-medium">Submission Deadline:</span>
                        <p className="font-bold text-error text-sm mt-0.5">
                          {inspectTender.submission_deadline || "Active"}
                        </p>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-medium">Portal Reference Link:</span>
                        <p className="mt-0.5 truncate">
                          {inspectTender.source_url ? (
                            <a
                              href={inspectTender.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-secondary font-bold hover:underline"
                            >
                              Open Portal Notice ↗
                            </a>
                          ) : (
                            <span className="text-on-surface-variant">N/A</span>
                          )}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Mandatory Documents Checklist */}
                  <div className="p-5 rounded-2xl bg-surface neu-flat flex flex-col gap-3">
                    <h3 className="font-serif text-base font-bold text-primary flex items-center gap-2">
                      <span className="material-symbols-outlined text-secondary">checklist</span>
                      <span>Mandatory Qualification Documents (From Eye Button Preview)</span>
                    </h3>
                    {inspectTender.mandatory_documents && inspectTender.mandatory_documents.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {inspectTender.mandatory_documents.map((doc, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded-xl bg-surface-container-lowest neu-pressed text-xs flex items-center gap-2"
                          >
                            <span className="material-symbols-outlined text-emerald-600 text-sm font-bold">check_circle</span>
                            <span className="font-medium text-on-surface">{doc}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-on-surface-variant italic">
                        Standard statutory documents required (GST, PAN, EMD, MSME Registration).
                      </p>
                    )}
                  </div>
                </>
              ) : inspectTab === "clauses" ? (
                <div className="flex flex-col gap-4">
                  {inspectTender.extraction && inspectTender.extraction.verbatim_clauses && inspectTender.extraction.verbatim_clauses.length > 0 ? (
                    inspectTender.extraction.verbatim_clauses.map((clause: any, idx: number) => (
                      <div key={idx} className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-primary font-serif">
                            {clause.clause_title || `Clause #${idx + 1}`}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-bold">
                            Page {clause.page || 1}
                          </span>
                        </div>
                        <p className="text-xs text-on-surface font-mono bg-white/70 p-3 rounded-xl border border-gray-100">
                          &ldquo;{clause.verbatim_text || clause.quote}&rdquo;
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="p-8 text-center bg-surface neu-pressed rounded-2xl text-xs text-on-surface-variant">
                      No verbatim PDF clauses parsed yet for this notice.
                    </div>
                  )}
                </div>
              ) : inspectTab === "rulepack" ? (
                <div className="flex flex-col gap-4">
                  {inspectTender.rule_pack ? (
                    <pre className="p-4 rounded-2xl bg-gray-900 text-emerald-400 text-xs font-mono overflow-x-auto max-h-[500px]">
                      {JSON.stringify(inspectTender.rule_pack, null, 2)}
                    </pre>
                  ) : (
                    <div className="p-8 text-center bg-surface neu-pressed rounded-2xl text-xs text-on-surface-variant">
                      No RulePack generated for this tender.
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <pre className="p-4 rounded-2xl bg-gray-900 text-amber-300 text-xs font-mono overflow-x-auto max-h-[500px]">
                    {JSON.stringify(inspectTender, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-200/80 bg-surface-container-low flex items-center justify-between">
              <span className="text-xs text-on-surface-variant font-mono">
                ID: {inspectTender.tender_id}
              </span>
              <div className="flex items-center gap-3">
                <Link
                  href={`/audit?tender_id=${encodeURIComponent(inspectTender.tender_number)}`}
                  className="px-5 py-2 rounded-full bg-primary text-white text-xs font-bold shadow-md hover:bg-primary/90 transition-all cursor-pointer flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-base">verified</span>
                  <span>Open Verification Matrix</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TENDER PDF UPLOAD MODAL */}
      {/* ========================================================================= */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-container-lowest neu-flat rounded-3xl w-full max-w-lg p-6 sm:p-8 flex flex-col gap-5 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-serif text-2xl font-bold text-primary">Upload Tender PDF</h2>
                <p className="text-xs text-on-surface-variant mt-1">
                  Upload an Indian public procurement NIT, RFP, or Tender document.
                </p>
              </div>
              <button
                onClick={() => {
                  setIsUploadModalOpen(false);
                  setUploadFile(null);
                  setUploadStatus("");
                }}
                className="w-8 h-8 rounded-full neu-button flex items-center justify-center text-on-surface-variant hover:text-on-surface cursor-pointer"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            <form onSubmit={handleFileUpload} className="flex flex-col gap-4">
              <div className="border-2 border-dashed border-gray-300 rounded-2xl p-6 text-center flex flex-col items-center justify-center gap-3 bg-surface hover:border-secondary transition-all">
                <span className="material-symbols-outlined text-4xl text-secondary">cloud_upload</span>
                <div>
                  <label htmlFor="pdfInput" className="text-xs font-bold text-secondary hover:underline cursor-pointer">
                    Click to select tender document
                  </label>
                  <input
                    id="pdfInput"
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setUploadFile(e.target.files ? e.target.files[0] : null)}
                    className="hidden"
                  />
                  <p className="text-[11px] text-on-surface-variant mt-0.5">Supports scanned &amp; digital Indian PDFs</p>
                </div>
                {uploadFile && (
                  <div className="px-3 py-1.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-xs font-mono font-bold flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
                    <span className="truncate max-w-[200px]">{uploadFile.name}</span>
                  </div>
                )}
              </div>

              {uploadStatus && (
                <div className="p-3 rounded-xl bg-surface neu-pressed text-xs text-secondary font-medium flex items-center gap-2">
                  {isUploading && <div className="w-4 h-4 border-2 border-secondary border-t-transparent rounded-full animate-spin shrink-0" />}
                  <span>{uploadStatus}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  className="px-4 py-2 rounded-full neu-button text-xs font-bold text-on-surface-variant cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!uploadFile || isUploading}
                  className="px-5 py-2 rounded-full bg-secondary text-white text-xs font-bold shadow-md hover:bg-secondary/90 transition-all cursor-pointer disabled:opacity-50"
                >
                  {isUploading ? "Processing..." : "Extract & Ingest"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function OpenTendersPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-surface flex items-center justify-center text-sm text-[#735368]">Loading tenders workspace...</div>}>
      <TendersListInner />
    </Suspense>
  );
}
