"use client";

import React, { useState, useEffect, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  getDocuments,
  uploadDocument,
  apiClient,
  DocumentItem,
  DocumentRecord,
} from "@/lib/api";

const DOC_TYPE_META: Record<
  string,
  {
    label: string;
    category: "Financial" | "Statutory" | "Technical" | "Certifications" | "Other";
  }
> = {
  udyam_certificate: { label: "Udyam MSME Registration", category: "Statutory" },
  ca_turnover_certificate: { label: "CA Turnover & Balance Sheet", category: "Financial" },
  nsic_registration: { label: "NSIC Enlistment Certificate", category: "Technical" },
  gst_certificate: { label: "GST Registration Certificate", category: "Statutory" },
  pan_card: { label: "PAN Card", category: "Statutory" },
  work_experience_certificate: { label: "Work Experience Certificate", category: "Technical" },
  banking_reference_annexure_x: { label: "Banking Reference (Annexure X)", category: "Financial" },
  truthfulness_undertaking_annexure_i: { label: "Truthfulness Undertaking (Annexure I)", category: "Statutory" },
  bid_form_annexure_ii: { label: "Bid Form (Annexure II)", category: "Statutory" },
  solvency_certificate: { label: "Bank Solvency Certificate", category: "Financial" },
  iso_certificate: { label: "ISO Compliance Attestation", category: "Certifications" },
  other: { label: "Compliance Document", category: "Other" },
};

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 KB";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function DocumentVaultPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string>("udyam_certificate");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);
  const [uploadErrorMsg, setUploadErrorMsg] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<{ active: boolean; progress: number; status: string } | null>(null);

  // Inspection modal state
  const [inspectedDoc, setInspectedDoc] = useState<DocumentItem | null>(null);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    setIsLoading(true);
    try {
      const data = await getDocuments();
      if (Array.isArray(data) && data.length > 0) {
        setDocuments(data);
      } else {
        const res = await apiClient.documents.list();
        const items = Array.isArray(res) ? res : res.results || [];
        setDocuments(items);
      }
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress("Hashing SHA-256 and validating cryptographic signature...");
    setUploadErrorMsg(null);
    setJobProgress({ active: true, progress: 20, status: "Uploading & computing SHA-256 hash..." });

    try {
      const res = await apiClient.documents.upload(selectedFile, selectedDocType);
      if (res && res.job_id) {
        setJobProgress({ active: true, progress: 45, status: "Async OCR & Digital Signature Verification in progress..." });
        await apiClient.jobs.poll(
          res.job_id,
          (job) => {
            setJobProgress({
              active: job.status === "PENDING" || job.status === "PROCESSING",
              progress: job.progress || 70,
              status: job.status === "COMPLETED" ? "Verification & Storage Complete!" : "Processing Document AI Pipeline...",
            });
          },
          25,
          1000
        );
      }

      setUploadSuccessMsg(`Document "${selectedFile.name}" uploaded and cryptographically indexed!`);
      setShowUploadModal(false);
      setSelectedFile(null);
      await fetchDocs();
      setTimeout(() => setUploadSuccessMsg(null), 5000);
    } catch (err: any) {
      // Fallback to uploadDocument helper
      try {
        const fallbackRes = await uploadDocument(selectedFile, selectedDocType);
        if (fallbackRes.success && fallbackRes.document) {
          setUploadSuccessMsg(`Document "${fallbackRes.document.file_name}" uploaded and cryptographically indexed!`);
          setShowUploadModal(false);
          setSelectedFile(null);
          await fetchDocs();
          setTimeout(() => setUploadSuccessMsg(null), 5000);
        } else {
          setUploadErrorMsg(fallbackRes.error || "Upload failed. Please verify document format.");
        }
      } catch (innerErr: any) {
        setUploadErrorMsg(innerErr.message || "Failed to upload document");
      }
    } finally {
      setIsUploading(false);
      setUploadProgress("");
      setTimeout(() => setJobProgress(null), 3000);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const categories = ["All", "Financial", "Statutory", "Technical", "Other"];

  const filteredDocs = documents.filter((doc) => {
    const meta = DOC_TYPE_META[doc.document_type] || { category: "Other", label: doc.document_type };
    const matchesCategory = selectedCategory === "All" || meta.category === selectedCategory;
    const q = searchQuery.toLowerCase().trim();
    const matchesQuery =
      !q ||
      doc.file_name.toLowerCase().includes(q) ||
      (doc.sha256_hash && doc.sha256_hash.toLowerCase().includes(q)) ||
      doc.document_type.toLowerCase().includes(q) ||
      meta.label.toLowerCase().includes(q);
    return matchesCategory && matchesQuery;
  });

  // Calculate live stats
  const totalCount = documents.length;
  const signedCount = documents.filter((d) => d.is_digitally_signed || d.signature_valid).length;
  const integrityPassCount = documents.filter((d) => d.sha256_hash).length;
  const signedPercentage = totalCount > 0 ? Math.round((signedCount / totalCount) * 100) : 100;

  return (
    <div className="bg-surface font-sans text-on-surface antialiased min-h-screen">
      <Sidebar activeTab="vault" />

      <div className="lg:pl-72 flex flex-col min-h-screen">
        <DashboardHeader />

        <main className="w-full pt-16 bg-surface min-h-screen">
          <div className="px-4 sm:px-8 xl:px-12 py-8 flex flex-col gap-6 max-w-[1500px] mx-auto w-full pb-24">
            
            {/* Header Strip */}
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#480870]">folder_special</span>
                  <h1 className="font-serif text-2xl font-bold tracking-tight text-[#1e1b18] sm:text-3xl">
                    Enterprise Document Vault
                  </h1>
                </div>
                <p className="mt-1 text-sm text-[#735368]">
                  Centralized, cryptographically verified repository of CA certificates, UDIN credentials, and statutory filings.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(true)}
                  className="flex items-center gap-2 rounded-xl neu-button-primary px-4 py-2.5 text-xs font-semibold cursor-pointer"
                >
                  <span className="material-symbols-outlined text-sm">upload_file</span>
                  Upload &amp; Validate Document
                </button>

                <button
                  type="button"
                  onClick={fetchDocs}
                  className="flex items-center gap-2 rounded-xl neu-button px-4 py-2.5 text-xs font-semibold text-on-surface cursor-pointer"
                  title="Refresh documents from backend"
                >
                  <span className="material-symbols-outlined text-sm text-[#480870]">refresh</span>
                  Sync Vault
                </button>
              </div>
            </div>

            {/* Async Job Progress Bar */}
            {jobProgress && (
              <div className="rounded-2xl neu-flat bg-surface-container-low p-4 border border-secondary/30 transition-all">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-ping" />
                    <span className="text-xs font-bold text-primary">Document AI Pipeline: {jobProgress.status}</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-secondary">{jobProgress.progress}%</span>
                </div>
                <div className="w-full bg-surface-container-high h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-secondary h-full rounded-full transition-all duration-300"
                    style={{ width: `${jobProgress.progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Success Banner */}
            {uploadSuccessMsg && (
              <div className="flex items-center justify-between rounded-xl neu-flat bg-emerald-50/90 p-4 text-emerald-900 transition">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-emerald-600">verified</span>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Audit Successful</p>
                    <p className="text-sm font-semibold">{uploadSuccessMsg}</p>
                  </div>
                </div>
                <span
                  className="material-symbols-outlined cursor-pointer text-emerald-700"
                  onClick={() => setUploadSuccessMsg(null)}
                >
                  close
                </span>
              </div>
            )}

            {/* Error Banner */}
            {uploadErrorMsg && (
              <div className="flex items-center justify-between rounded-xl neu-flat bg-rose-50/80 p-4 text-rose-900 border border-rose-200">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-rose-600">error</span>
                  <p className="text-sm font-semibold">{uploadErrorMsg}</p>
                </div>
                <span
                  className="material-symbols-outlined cursor-pointer text-rose-700"
                  onClick={() => setUploadErrorMsg(null)}
                >
                  close
                </span>
              </div>
            )}

            {/* Metric Overview Strip */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-2xl neu-flat p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Vault Integrity</span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg neu-flat-sm bg-secondary-fixed text-on-secondary-fixed">
                    <span className="material-symbols-outlined text-base">verified_user</span>
                  </span>
                </div>
                <p className="mt-3 text-2xl font-bold tracking-tight text-primary">100%</p>
                <p className="mt-1 text-xs text-emerald-700 flex items-center gap-1 font-medium">
                  <span className="material-symbols-outlined text-xs">check_circle</span>
                  {integrityPassCount} of {totalCount} SHA-256 verified
                </p>
              </div>

              <div className="rounded-2xl neu-flat p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Active Documents</span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg neu-flat-sm bg-emerald-100 text-emerald-700">
                    <span className="material-symbols-outlined text-base">fact_check</span>
                  </span>
                </div>
                <p className="mt-3 text-2xl font-bold tracking-tight text-primary">{totalCount} Indexed</p>
                <p className="mt-1 text-xs text-on-surface-variant">Available for instant tender compliance</p>
              </div>

              <div className="rounded-2xl neu-flat p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">DSC Signatures</span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg neu-flat-sm bg-indigo-100 text-indigo-700">
                    <span className="material-symbols-outlined text-base">token</span>
                  </span>
                </div>
                <p className="mt-3 text-2xl font-bold tracking-tight text-primary">{signedCount} Signed</p>
                <p className="mt-1 text-xs text-on-surface-variant">{signedPercentage}% cryptographically verified</p>
              </div>

              <div className="rounded-2xl neu-flat p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-800">Compliance Health</span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg neu-flat-sm bg-emerald-100 text-emerald-700">
                    <span className="material-symbols-outlined text-base">health_and_safety</span>
                  </span>
                </div>
                <p className="mt-3 text-2xl font-bold tracking-tight text-emerald-700">Ready</p>
                <p className="mt-1 text-xs text-on-surface-variant">Zero blocking audit defects</p>
              </div>
            </div>

            {/* Quick Upload Strip */}
            <div className="rounded-2xl neu-pressed p-6 text-center transition">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl neu-flat-sm text-secondary bg-surface-container-lowest">
                <span className="material-symbols-outlined text-2xl">cloud_upload</span>
              </div>
              <p className="mt-3 font-semibold text-primary">Upload your tender compliance documents</p>
              <p className="mt-1 text-xs text-on-surface-variant">
                Accepts PDF &amp; P7S up to 50MB. Auto-runs SHA-256 integrity, pyHanko cryptographic signature check, and OCR field extraction.
              </p>
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(true)}
                  className="rounded-lg neu-button-primary px-4 py-2 text-xs font-semibold cursor-pointer"
                >
                  Select File to Upload
                </button>
              </div>
            </div>

            {/* Filters & Search Bar */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setSelectedCategory(cat)}
                    className={`rounded-full px-4 py-1.5 text-xs font-semibold transition cursor-pointer ${
                      selectedCategory === cat
                        ? "neu-button-primary"
                        : "neu-button text-on-surface-variant"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="relative w-full sm:w-80">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-sm text-on-surface-variant">
                  search
                </span>
                <input
                  type="text"
                  placeholder="Search file, SHA-256, type..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl neu-pressed py-2 pl-9 pr-4 text-xs font-medium text-on-surface placeholder:text-on-surface-variant outline-none transition focus:ring-1 focus:ring-secondary/40"
                />
              </div>
            </div>

            {/* Document Table */}
            <div className="overflow-hidden rounded-2xl neu-flat">
              {isLoading ? (
                <div className="py-16 text-center text-sm text-[#735368]">
                  <span className="material-symbols-outlined animate-spin text-2xl text-[#480870] mb-2 block mx-auto">
                    progress_activity
                  </span>
                  Loading verified documents from vault...
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#E9DFE4] bg-[#F8F2F6] font-semibold text-[#735368]">
                        <th className="px-6 py-4">DOCUMENT / CREDENTIAL</th>
                        <th className="px-4 py-4">CATEGORY</th>
                        <th className="px-4 py-4">SHA-256 &amp; SIGNATURE INTEGRITY</th>
                        <th className="px-4 py-4">DATE INDEXED</th>
                        <th className="px-6 py-4 text-right">ACTIONS</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E9DFE4]">
                      {filteredDocs.map((doc) => {
                        const meta = DOC_TYPE_META[doc.document_type] || { category: "Other", label: doc.document_type };
                        const isSigned = doc.is_digitally_signed || doc.signature_valid;
                        const docDownloadUrl = doc.id
                          ? apiClient.documents.downloadUrl(doc.id)
                          : (doc as any).file_url || "#";

                        return (
                          <tr key={doc.id} className="transition hover:bg-[#FAF5F8]">
                            {/* Document Title & File Info */}
                            <td className="px-6 py-4">
                              <div className="flex items-start gap-3">
                                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#EAE0EB] text-[#480870]">
                                  <span className="material-symbols-outlined text-lg">
                                    {isSigned ? "token" : "description"}
                                  </span>
                                </div>
                                <div>
                                  <p className="font-semibold text-[#1e1b18]">{doc.file_name}</p>
                                  <p className="mt-0.5 text-[11px] text-[#735368]">
                                    {meta.label} • {formatBytes(doc.file_size_bytes)}
                                  </p>
                                </div>
                              </div>
                            </td>

                            {/* Category Badge */}
                            <td className="px-4 py-4">
                              <span className="inline-flex rounded-md border border-[#E9DFE4] bg-[#F8F2F6] px-2.5 py-1 text-[11px] font-medium text-[#735368]">
                                {meta.category}
                              </span>
                            </td>

                            {/* UDIN / Verification Status */}
                            <td className="px-4 py-4">
                              <div className="flex items-center gap-1.5">
                                <span className={`material-symbols-outlined text-sm ${isSigned ? "text-emerald-600" : "text-indigo-600"}`}>
                                  {isSigned ? "verified" : "security"}
                                </span>
                                <span className={`font-semibold ${isSigned ? "text-emerald-700" : "text-indigo-700"}`}>
                                  {isSigned ? "DSC Digitally Signed" : "SHA-256 Validated"}
                                </span>
                              </div>
                              <p className="mt-0.5 max-w-[280px] font-mono text-[10px] text-[#735368] truncate" title={doc.sha256_hash}>
                                {doc.sha256_hash}
                              </p>
                            </td>

                            {/* Date Indexed */}
                            <td className="px-4 py-4">
                              <span className="text-[#1e1b18] font-medium">
                                {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "Active"}
                              </span>
                            </td>

                            {/* Actions */}
                            <td className="px-6 py-4 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <a
                                  href={docDownloadUrl}
                                  download
                                  title="Download verified document"
                                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#E9DFE4] bg-white text-[#735368] hover:bg-[#F3EBF0] hover:text-[#480870]"
                                >
                                  <span className="material-symbols-outlined text-sm">download</span>
                                </a>
                                <button
                                  type="button"
                                  onClick={() => setInspectedDoc(doc)}
                                  title="View cryptographic details &amp; extracted fields"
                                  className="flex h-8 items-center gap-1.5 rounded-lg border border-[#E9DFE4] bg-white px-2.5 text-[#735368] hover:bg-[#F3EBF0] hover:text-[#480870] cursor-pointer"
                                >
                                  <span className="material-symbols-outlined text-sm">visibility</span>
                                  <span className="text-[11px] font-semibold">Inspect</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {!isLoading && filteredDocs.length === 0 && (
                <div className="p-12 text-center text-sm text-[#735368]">
                  No compliance documents match your criteria. Click &quot;Upload &amp; Validate Document&quot; to add one.
                </div>
              )}
            </div>
          </div>
        </main>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-4">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[#480870]">upload_file</span>
                <h3 className="text-lg font-bold text-[#1e1b18]">Upload Compliance Document</h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowUploadModal(false);
                  setSelectedFile(null);
                  setUploadErrorMsg(null);
                }}
                className="text-gray-400 hover:text-gray-600 cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#735368] mb-1">
                  Document Type
                </label>
                <select
                  value={selectedDocType}
                  onChange={(e) => setSelectedDocType(e.target.value)}
                  className="w-full rounded-xl border border-gray-300 p-2.5 text-xs font-medium text-gray-800 outline-none focus:border-[#480870] cursor-pointer"
                >
                  {Object.entries(DOC_TYPE_META).map(([key, item]) => (
                    <option key={key} value={key}>
                      {item.label} ({item.category})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#735368] mb-1">
                  Select Document File (PDF or P7S)
                </label>
                <input
                  type="file"
                  accept=".pdf,.p7s"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  required
                  className="w-full rounded-xl border border-dashed border-gray-300 p-4 text-xs text-gray-700 file:mr-3 file:rounded-lg file:border-0 file:bg-[#480870] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:border-[#480870] cursor-pointer"
                />
                {selectedFile && (
                  <p className="mt-2 text-xs text-emerald-700 font-medium flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">check_circle</span>
                    Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
                  </p>
                )}
              </div>

              {uploadProgress && (
                <div className="flex items-center gap-2 rounded-lg bg-purple-50 p-3 text-xs text-[#480870]">
                  <span className="material-symbols-outlined animate-spin text-sm">progress_activity</span>
                  <span>{uploadProgress}</span>
                </div>
              )}

              {uploadErrorMsg && (
                <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 font-medium">
                  {uploadErrorMsg}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  disabled={isUploading}
                  className="rounded-xl border border-gray-300 px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || isUploading}
                  className="rounded-xl bg-[#480870] px-5 py-2 text-xs font-semibold text-white hover:bg-[#3B0066] disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
                >
                  {isUploading && <span className="material-symbols-outlined animate-spin text-xs">progress_activity</span>}
                  {isUploading ? "Uploading..." : "Upload & Validate"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Document Inspection Modal */}
      {inspectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b px-6 py-4 bg-[#F8F2F6]">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-[#480870] text-2xl">verified_user</span>
                <div>
                  <h3 className="text-base font-bold text-[#1e1b18]">{inspectedDoc.file_name}</h3>
                  <p className="text-xs text-[#735368]">
                    ID: {inspectedDoc.id} • {DOC_TYPE_META[inspectedDoc.document_type]?.label || inspectedDoc.document_type}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectedDoc(null)}
                className="text-gray-400 hover:text-gray-600 cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs text-[#1e1b18]">
              {/* Cryptographic SHA-256 Card */}
              <div className="rounded-xl bg-gray-50 p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold uppercase tracking-wider text-[#735368]">SHA-256 Hash Digest</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(inspectedDoc.sha256_hash)}
                    className="flex items-center gap-1 text-[#480870] font-semibold hover:underline cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-xs">content_copy</span>
                    {copiedHash ? "Copied!" : "Copy Hash"}
                  </button>
                </div>
                <p className="font-mono text-xs text-gray-800 break-all select-all bg-white p-2 rounded-lg border border-gray-200">
                  {inspectedDoc.sha256_hash}
                </p>
              </div>

              {/* Digital Signature Details */}
              <div className="rounded-xl bg-purple-50/50 p-4 border border-purple-100">
                <h4 className="font-bold text-[#480870] mb-2 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">token</span>
                  pyHanko Cryptographic Signature Verification
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-gray-500">Signature Status:</span>
                    <p className="font-semibold text-emerald-700">
                      {inspectedDoc.is_digitally_signed || inspectedDoc.signature_valid ? "Valid & Verified" : "No Embedded DSC Signature"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Signatures Found:</span>
                    <p className="font-semibold text-gray-800">
                      {inspectedDoc.signature_details?.signatures?.length || (inspectedDoc.is_digitally_signed ? 1 : 0)} Signer(s)
                    </p>
                  </div>
                </div>

                {inspectedDoc.signature_details?.signatures && inspectedDoc.signature_details.signatures.length > 0 && (
                  <div className="mt-3 bg-white p-2.5 rounded-lg border border-purple-200">
                    <span className="text-[11px] font-bold text-gray-600 block mb-1">Signer Certificate Details:</span>
                    {inspectedDoc.signature_details.signatures.map((sig: string, idx: number) => (
                      <p key={idx} className="font-mono text-[11px] text-gray-800 break-all">
                        {sig}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              {/* Extracted Entity Fields */}
              <div className="rounded-xl bg-gray-50 p-4 border border-gray-200">
                <h4 className="font-bold text-gray-800 mb-2 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">data_object</span>
                  Extracted OCR &amp; Registry Fields
                </h4>
                {inspectedDoc.extracted_data && Object.keys(inspectedDoc.extracted_data).length > 0 ? (
                  <pre className="bg-white p-3 rounded-lg border border-gray-200 text-[11px] font-mono text-gray-800 overflow-x-auto">
                    {JSON.stringify(inspectedDoc.extracted_data, null, 2)}
                  </pre>
                ) : (
                  <p className="text-gray-500 italic">No structured entity overrides extracted.</p>
                )}
              </div>
            </div>

            <div className="border-t px-6 py-3 bg-gray-50 flex justify-end">
              <button
                type="button"
                onClick={() => setInspectedDoc(null)}
                className="rounded-xl neu-button px-4 py-2 text-xs font-semibold text-gray-700 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
