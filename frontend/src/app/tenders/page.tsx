"use client";

import React, { useState, useEffect, useTransition, Suspense, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  searchTenders,
  getTenderDetail,
  uploadTenderPdf,
  intakeTender,
  getPortals,
  ALL_STATE_PORTALS,
  PortalRegistryItem,
  TenderItem,
  apiClient,
} from "@/lib/api";
import { formatINR } from "@/lib/utils";

function TendersListInner() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("query") || searchParams.get("q") || "";
  const initialState = searchParams.get("state") || "All";

  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPortal, setSelectedPortal] = useState<string>("All");
  const [selectedState, setSelectedState] = useState<string>(initialState);
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);
  const [isSearching, startTransition] = useTransition();

  // State Portals Directory modal state
  const [isPortalsModalOpen, setIsPortalsModalOpen] = useState<boolean>(false);
  const [portalsList, setPortalsList] = useState<PortalRegistryItem[]>(ALL_STATE_PORTALS);
  const [portalFilterType, setPortalFilterType] = useState<string>("All");
  const [portalSearchText, setPortalSearchText] = useState<string>("");

  // Selected tender for deep inspection modal
  const [inspectTender, setInspectTender] = useState<TenderItem | null>(null);
  const [inspectLoading, setInspectLoading] = useState<boolean>(false);
  const [inspectTab, setInspectTab] = useState<"skim" | "clauses" | "rulepack" | "json">("skim");

  // PDF Upload modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Live Scraper / Intake modal state
  const [isScraperModalOpen, setIsScraperModalOpen] = useState<boolean>(false);
  const [scraperInput, setScraperInput] = useState<string>("");
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [isScraping, setIsScraping] = useState<boolean>(false);
  const [scraperStatus, setScraperStatus] = useState<string>("");
  const [scraperError, setScraperError] = useState<string | null>(null);
  const [scraperSuccessData, setScraperSuccessData] = useState<any | null>(null);

  // Fetch initial tenders on load
  const loadTenders = async (q?: string, state?: string) => {
    setLoading(true);
    setError(null);
    try {
      const activeState = state !== undefined ? state : selectedState;
      const res = await searchTenders({
        q: q !== undefined ? q : searchQuery,
        state: activeState !== "All" ? activeState : undefined,
        limit: 50,
      });
      if (res.success && Array.isArray(res.results)) {
        setTenders(res.results);
      } else {
        // Fallback to apiClient.tenders.list()
        try {
          const apiRes = await apiClient.tenders.list();
          const items = Array.isArray(apiRes) ? apiRes : apiRes.results || [];
          setTenders(items as any);
        } catch {
          setTenders([]);
        }
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
    if (initialQuery || initialState !== "All") {
      setSearchQuery(initialQuery);
      setSelectedState(initialState);
      loadTenders(initialQuery, initialState);
    } else {
      loadTenders();
    }
  }, [initialQuery, initialState]);

  // Load official portal directory from backend on mount
  useEffect(() => {
    getPortals().then((res) => {
      if (res.success && Array.isArray(res.portals) && res.portals.length > 0) {
        setPortalsList(res.portals);
      }
    });
  }, []);

  // If tender_id is provided in URL, auto-inspect it
  useEffect(() => {
    const targetId = searchParams.get("tender_id");
    if (targetId && tenders.length > 0) {
      const match = tenders.find((t) => t.tender_id === targetId || t.tender_number === targetId);
      if (match && (!inspectTender || (inspectTender.tender_id !== match.tender_id && inspectTender.tender_number !== match.tender_number))) {
        handleInspect(match.tender_number || match.tender_id);
      }
    }
  }, [searchParams.get("tender_id"), tenders]);

  const displayedPortals = portalsList.filter((p) => {
    if (portalFilterType !== "All" && p.type !== portalFilterType) return false;
    if (portalSearchText.trim()) {
      const q = portalSearchText.toLowerCase();
      return (
        p.name.toLowerCase().includes(q) ||
        p.domain.toLowerCase().includes(q) ||
        p.code.toLowerCase().includes(q) ||
        p.portal_name.toLowerCase().includes(q)
      );
    }
    return true;
  });

  // Handle live search (with automatic URL detection)
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (query.startsWith("http://") || query.startsWith("https://")) {
      setScraperInput(query);
      setIsScraperModalOpen(true);
      handleRunScraper(query);
      return;
    }
    startTransition(() => {
      loadTenders(query, selectedState);
    });
  };

  // Inspect specific tender with eye-button preview
  const handleInspect = async (tenderNumber: string) => {
    setInspectLoading(true);
    setInspectTab("skim");
    try {
      const detailed = await getTenderDetail(tenderNumber, "detailed");
      setInspectTender(detailed || tenders.find((t) => t.tender_number === tenderNumber) || null);
    } catch {
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

  // Handle Live Portal Scraper execution
  const handleRunScraper = async (customIdentifier?: string, customForce?: boolean) => {
    const target = (customIdentifier || scraperInput).trim();
    if (!target) return;

    setIsScraping(true);
    setScraperError(null);
    setScraperSuccessData(null);
    setScraperStatus("Connecting to portal & resolving tender notice...");

    const force = customForce !== undefined ? customForce : forceRefresh;

    try {
      const progressTimer = setTimeout(() => {
        setScraperStatus("Solving CAPTCHA & extracting verbatim clauses...");
      }, 1200);

      const res = await intakeTender(target, force);
      clearTimeout(progressTimer);

      if (res.success) {
        setScraperStatus("Tender successfully ingested & RulePack synthesized!");
        setScraperSuccessData(res);
        await loadTenders();
        setTimeout(() => {
          setIsScraperModalOpen(false);
          setIsScraping(false);
          setScraperStatus("");
          setScraperInput("");
          const lookupKey = res.tender_number || res.tender_id;
          if (lookupKey) {
            handleInspect(lookupKey);
          }
        }, 1000);
      } else {
        setIsScraping(false);
        setScraperError(res.error || "Portal scraping failed. Please verify the URL or Tender Number.");
      }
    } catch (err: any) {
      setIsScraping(false);
      setScraperError(err.message || "Portal scraper encountered a connection error.");
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
          <div className="flex flex-col w-full max-w-[1500px] mx-auto px-4 sm:px-8 xl:px-12 py-8">
            {/* Page Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
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
                  Live indexed discovery across GeM, CPPP, IREPS &amp; 36 Indian State &amp; UT portals.
                </p>
              </div>

              {/* Status / Quick Stats */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  onClick={() => setIsPortalsModalOpen(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-surface-container-high text-primary text-xs font-bold neu-button hover:bg-surface-container-highest transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-base text-primary">public</span>
                  <span>State Portals ({portalsList.length})</span>
                </button>
                <button
                  onClick={() => {
                    setScraperError(null);
                    setScraperSuccessData(null);
                    setIsScraperModalOpen(true);
                  }}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary text-white text-xs font-bold shadow-md hover:bg-primary/90 transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-base animate-pulse">satellite_alt</span>
                  <span>Live Portal Scraper</span>
                </button>
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
            <div className="bg-surface-container-lowest neu-flat p-4 sm:p-5 rounded-2xl flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 mt-6">
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

              {/* State Filter Dropdown + Search input */}
              <form onSubmit={handleSearch} className="relative flex-1 max-w-xl flex items-center gap-2">
                <select
                  value={selectedState}
                  onChange={(e) => {
                    const newState = e.target.value;
                    setSelectedState(newState);
                    loadTenders(searchQuery, newState);
                  }}
                  aria-label="Filter by state"
                  className="px-3 py-2.5 rounded-xl neu-pressed text-xs font-semibold text-on-surface bg-surface-container-low focus:outline-none cursor-pointer border border-outline-variant/30"
                >
                  <option value="All">All States</option>
                  <option value="Bihar">Bihar</option>
                  <option value="Delhi">Delhi</option>
                  <option value="Maharashtra">Maharashtra</option>
                  <option value="Uttar Pradesh">Uttar Pradesh</option>
                  <option value="Rajasthan">Rajasthan</option>
                  <option value="Gujarat">Gujarat</option>
                  <option value="Karnataka">Karnataka</option>
                  <option value="Tamil Nadu">Tamil Nadu</option>
                  <option value="West Bengal">West Bengal</option>
                  <option value="Madhya Pradesh">Madhya Pradesh</option>
                  <option value="Haryana">Haryana</option>
                  <option value="Punjab">Punjab</option>
                  <option value="Jharkhand">Jharkhand</option>
                  <option value="Odisha">Odisha</option>
                  <option value="Telangana">Telangana</option>
                  <option value="Andhra Pradesh">Andhra Pradesh</option>
                </select>

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
              <div className="p-4 rounded-xl bg-error-container text-on-error-container text-xs flex items-center gap-2 mt-4">
                <span className="material-symbols-outlined text-lg">error</span>
                <span>{error}</span>
              </div>
            )}

            {/* Loading Skeleton */}
            {loading && (
              <div className="flex flex-col gap-4 py-12 items-center justify-center">
                <div className="w-10 h-10 border-4 border-secondary border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-on-surface-variant font-medium">Querying live backend discovery index...</span>
              </div>
            )}

            {/* Empty State */}
            {!loading && filteredTenders.length === 0 && (
              <div className="p-12 text-center bg-surface-container-lowest neu-flat rounded-2xl flex flex-col items-center justify-center gap-3 mt-6">
                <span className="material-symbols-outlined text-4xl text-on-surface-variant">search_off</span>
                <h3 className="font-serif text-lg font-bold text-primary">No Matching Tenders Found</h3>
                <p className="text-xs text-on-surface-variant max-w-md">
                  Try adjusting your search criteria, searching for a tender number (e.g. &apos;141349&apos; or &apos;2026_HRY_530295_1&apos;), or uploading a tender PDF.
                </p>
                <div className="flex items-center gap-3 mt-2 flex-wrap justify-center">
                  {searchQuery && (
                    <button
                      onClick={() => {
                        setScraperInput(searchQuery);
                        setScraperError(null);
                        setScraperSuccessData(null);
                        setIsScraperModalOpen(true);
                      }}
                      className="px-4 py-2 rounded-full bg-secondary text-white text-xs font-bold shadow-md hover:bg-secondary/90 transition-all cursor-pointer flex items-center gap-1.5"
                    >
                      <span className="material-symbols-outlined text-base">satellite_alt</span>
                      <span>Scrape &quot;{searchQuery}&quot; Live</span>
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setSearchQuery("");
                      setSelectedPortal("All");
                      setSelectedState("All");
                      loadTenders("", "All");
                    }}
                    className="px-4 py-2 rounded-full neu-button text-xs font-bold text-primary cursor-pointer"
                  >
                    Reset All Filters
                  </button>
                </div>
              </div>
            )}

            {/* Live Tenders List */}
            {!loading && (
              <div className="flex flex-col gap-4 mt-6">
                {filteredTenders.map((tender) => {
                  const val = tender.estimated_value_inr;
                  const valStr = val ? formatINR(val) : "Not Specified";
                  const emd = tender.emd_amount_inr;
                  const emdStr = emd ? formatINR(emd) : "Exempted / Nil";
                  const portal = tender.portal || "Government Portal";

                  return (
                    <div
                      key={tender.tender_id || tender.tender_number}
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
                ID: {inspectTender.tender_id || inspectTender.tender_number}
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
      {/* LIVE PORTAL SCRAPER / INTAKE MODAL */}
      {/* ========================================================================= */}
      {isScraperModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-surface-container-lowest neu-flat rounded-3xl w-full max-w-xl p-6 sm:p-8 flex flex-col gap-5 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  <span className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider">
                    Universal Multi-Engine Portal Scraper
                  </span>
                </div>
                <h2 className="font-serif text-2xl font-bold text-primary">Live Tender Intake</h2>
                <p className="text-xs text-on-surface-variant mt-1">
                  Scrape tenders in real-time from GeM, CPPP, State Portals (Bihar eProc2, Haryana), or Infralens mirrors.
                </p>
              </div>
              <button
                onClick={() => {
                  if (!isScraping) {
                    setIsScraperModalOpen(false);
                    setScraperError(null);
                    setScraperStatus("");
                  }
                }}
                disabled={isScraping}
                className="w-8 h-8 rounded-full neu-button flex items-center justify-center text-on-surface-variant hover:text-on-surface cursor-pointer disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            {/* State & UT Portal Quick Selector */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] uppercase font-bold text-on-surface-variant tracking-wider flex items-center justify-between">
                <span>Select from 36 State &amp; UT E-Procurement Portals:</span>
                <span className="text-primary font-semibold">Automatic URL lookup</span>
              </label>
              <select
                disabled={isScraping}
                onChange={(e) => {
                  if (e.target.value) {
                    setScraperInput(e.target.value);
                  }
                }}
                defaultValue=""
                className="w-full px-3 py-2 rounded-xl neu-pressed text-xs bg-surface text-on-surface focus:outline-none focus:ring-1 focus:ring-primary/40 font-medium cursor-pointer"
              >
                <option value="" disabled>-- Select Indian State / UT Portal ({portalsList.length} Portals Available) --</option>
                {portalsList.map((p) => (
                  <option key={p.code + p.name} value={p.url}>
                    {p.name} ({p.code}) — {p.domain} [{p.engine}]
                  </option>
                ))}
              </select>
            </div>

            {/* Quick-Fill Presets */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-bold text-on-surface-variant tracking-wider">
                Quick-Select Verified Tenders:
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                {[
                  { label: "Jharkhand", val: "https://jharkhandtenders.gov.in" },
                  { label: "Bihar eProc2", val: "BIH/EPROC2/141349" },
                  { label: "Maharashtra", val: "https://mahatenders.gov.in" },
                  { label: "GeM Bid", val: "GEM/2026/B/894210" },
                  { label: "Haryana CPPP", val: "2026_HRY_530295_1" },
                ].map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    disabled={isScraping}
                    onClick={() => setScraperInput(preset.val)}
                    className="px-2.5 py-1 rounded-full text-[11px] font-mono neu-button hover:bg-surface-container text-on-surface-variant transition-all cursor-pointer disabled:opacity-50"
                  >
                    <span className="font-semibold text-primary">{preset.label}:</span> {preset.val.length > 22 ? preset.val.slice(0, 22) + "…" : preset.val}
                  </button>
                ))}
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleRunScraper();
              }}
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-on-surface flex items-center justify-between">
                  <span>Portal URL or Tender / Bid Reference Number</span>
                  {scraperInput && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-bold">
                      {scraperInput.toLowerCase().includes("gem")
                        ? "Detected: GeM Portal Bid"
                        : scraperInput.toLowerCase().includes("eproc2") || scraperInput.toLowerCase().includes("bihar")
                        ? "Detected: eProc2 Bihar Portal"
                        : scraperInput.toLowerCase().includes("cppp") || scraperInput.toLowerCase().includes("hry") || scraperInput.includes("_")
                        ? "Detected: CPPP / GePNIC Portal"
                        : scraperInput.startsWith("http")
                        ? "Detected: Direct Portal URL"
                        : "Detected: Tender Number"}
                    </span>
                  )}
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                    link
                  </span>
                  <input
                    type="text"
                    disabled={isScraping}
                    value={scraperInput}
                    onChange={(e) => setScraperInput(e.target.value)}
                    placeholder="e.g. GEM/2026/B/894210, https://tenders.infralens.in/..., or 2026_HRY_530295_1"
                    className="w-full pl-10 pr-4 py-2.5 neu-pressed rounded-xl text-xs sm:text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all font-mono disabled:opacity-60"
                  />
                </div>
              </div>

              {/* Force Refresh Toggle */}
              <div className="flex items-center gap-2">
                <input
                  id="forceRefreshCheck"
                  type="checkbox"
                  disabled={isScraping}
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                  className="rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
                />
                <label htmlFor="forceRefreshCheck" className="text-xs text-on-surface-variant cursor-pointer select-none">
                  Force Re-scrape (bypass cache and re-query live government portal)
                </label>
              </div>

              {/* Progress & Live Status View */}
              {isScraping && (
                <div className="p-4 rounded-2xl bg-surface neu-pressed flex flex-col gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin shrink-0" />
                    <span className="text-xs font-semibold text-primary">{scraperStatus}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 pt-1">
                    {[
                      { step: 1, label: "Connect" },
                      { step: 2, label: "Fetch Notice" },
                      { step: 3, label: "Extract Clauses" },
                      { step: 4, label: "RulePack" },
                    ].map((s) => (
                      <div key={s.step} className="flex flex-col items-center gap-1">
                        <div className="w-full h-1.5 rounded-full bg-surface-container-high overflow-hidden">
                          <div className="h-full bg-emerald-500 rounded-full animate-pulse w-full" />
                        </div>
                        <span className="text-[10px] text-on-surface-variant font-medium">{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Message Display */}
              {scraperError && (
                <div className="p-4 rounded-xl bg-error-container text-on-error-container text-xs flex flex-col gap-1.5">
                  <div className="flex items-center gap-2 font-bold">
                    <span className="material-symbols-outlined text-base">error</span>
                    <span>Scraper Encountered an Issue</span>
                  </div>
                  <p className="text-[11px] opacity-90">{scraperError}</p>
                  <p className="text-[10px] opacity-75 mt-1">
                    💡 Tip: If a state portal is undergoing maintenance or has a strict bot challenge, you can directly upload the tender PDF via &quot;Upload Tender PDF&quot;.
                  </p>
                </div>
              )}

              {/* Success Notification */}
              {scraperSuccessData && (
                <div className="p-3.5 rounded-xl bg-emerald-50 text-emerald-900 border border-emerald-200 text-xs flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-emerald-600 text-lg">check_circle</span>
                  <div className="flex flex-col">
                    <span className="font-bold">Tender Ingested Successfully!</span>
                    <span className="text-[11px] text-emerald-700">Opening detailed inspection workspace...</span>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  disabled={isScraping}
                  onClick={() => setIsScraperModalOpen(false)}
                  className="px-4 py-2 rounded-full neu-button text-xs font-bold text-on-surface-variant cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!scraperInput.trim() || isScraping}
                  className="px-6 py-2.5 rounded-full bg-primary text-white text-xs font-bold shadow-md hover:bg-primary/90 transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
                >
                  {isScraping ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Scraping Live Portal...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-base">travel_explore</span>
                      <span>Run Live Scraper</span>
                    </>
                  )}
                </button>
              </div>
            </form>
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

      {/* ========================================================================= */}
      {/* STATE PORTALS DIRECTORY & LOOKUP MODAL */}
      {/* ========================================================================= */}
      {isPortalsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-surface-container-lowest neu-flat rounded-3xl w-full max-w-4xl p-6 sm:p-8 flex flex-col gap-5 shadow-2xl max-h-[90vh]">
            <div className="flex items-start justify-between border-b border-gray-200/80 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="material-symbols-outlined text-primary text-xl">account_balance</span>
                  <span className="text-[10px] uppercase font-bold text-primary tracking-wider">
                    All-India Procurement Registry
                  </span>
                </div>
                <h2 className="font-serif text-2xl font-bold text-primary">
                  State &amp; National Procurement Portals ({displayedPortals.length})
                </h2>
                <p className="text-xs text-on-surface-variant mt-1">
                  Official e-Procurement portals covering all 28 Indian States, 8 Union Territories, and Central Marketplaces.
                </p>
              </div>
              <button
                onClick={() => setIsPortalsModalOpen(false)}
                className="w-8 h-8 rounded-full neu-button flex items-center justify-center text-on-surface-variant hover:text-on-surface cursor-pointer"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            {/* Filter & Search Bar */}
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="relative flex-1 w-full">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base">
                  search
                </span>
                <input
                  type="text"
                  value={portalSearchText}
                  onChange={(e) => setPortalSearchText(e.target.value)}
                  placeholder="Filter by state (e.g. Jharkhand, Maharashtra), code, or domain..."
                  className="w-full pl-9 pr-4 py-2 neu-pressed rounded-xl text-xs text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary/40 font-medium"
                />
              </div>

              <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto shrink-0">
                {["All", "State", "Union Territory", "Central"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setPortalFilterType(t)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-all shrink-0 ${
                      portalFilterType === t
                        ? "bg-primary text-white font-bold shadow-sm"
                        : "neu-button text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Portals Grid */}
            <div className="overflow-y-auto max-h-[55vh] pr-1 grid grid-cols-1 md:grid-cols-2 gap-3">
              {displayedPortals.map((p) => (
                <div
                  key={p.code + p.name}
                  className="p-3.5 rounded-2xl bg-surface neu-flat-sm flex flex-col justify-between gap-2.5 border border-transparent hover:border-primary/20 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-serif font-bold text-sm text-primary">{p.name}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-bold">
                          {p.code}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                            p.type === "State"
                              ? "bg-emerald-50 text-emerald-700"
                              : p.type === "Union Territory"
                              ? "bg-blue-50 text-blue-700"
                              : "bg-purple-50 text-purple-700"
                          }`}
                        >
                          {p.type}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface font-medium mt-0.5">{p.portal_name}</p>
                      <span className="text-[10px] text-on-surface-variant font-mono">{p.domain}</span>
                    </div>

                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open official portal website"
                      className="p-1.5 rounded-lg neu-button text-on-surface-variant hover:text-primary shrink-0"
                    >
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                    </a>
                  </div>

                  <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
                    <button
                      onClick={() => {
                        setIsPortalsModalOpen(false);
                        setSearchQuery(p.name);
                        loadTenders(p.name);
                      }}
                      className="flex-1 py-1 px-2.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-primary text-[11px] font-bold transition-all cursor-pointer flex items-center justify-center gap-1"
                    >
                      <span className="material-symbols-outlined text-xs">search</span>
                      <span>Lookup Tenders</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsPortalsModalOpen(false);
                        setScraperInput(p.url);
                        setScraperError(null);
                        setScraperSuccessData(null);
                        setIsScraperModalOpen(true);
                      }}
                      className="flex-1 py-1 px-2.5 rounded-lg bg-primary hover:bg-primary/90 text-white text-[11px] font-bold transition-all cursor-pointer flex items-center justify-center gap-1"
                    >
                      <span className="material-symbols-outlined text-xs">satellite_alt</span>
                      <span>Scrape Portal</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 border-t border-gray-200/80 bg-surface-container-low rounded-2xl flex items-center justify-between text-xs text-on-surface-variant">
              <span>Showing {displayedPortals.length} of {portalsList.length} verified government portals</span>
              <button
                onClick={() => setIsPortalsModalOpen(false)}
                className="px-4 py-1.5 rounded-full neu-button text-xs font-bold text-on-surface-variant hover:text-on-surface cursor-pointer"
              >
                Close Directory
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function OpenTendersPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-surface flex items-center justify-center">
          <div className="flex items-center gap-3 px-6 py-4 rounded-2xl neu-flat bg-white text-slate-700 text-sm font-semibold">
            <span className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></span>
            <span>Loading procurement tenders workspace...</span>
          </div>
        </div>
      }
    >
      <TendersListInner />
    </Suspense>
  );
}
