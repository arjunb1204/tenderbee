/**
 * TenderBee Central API Client
 * Connects frontend views directly to Django REST Framework backend APIs.
 */

export interface TenderItem {
  tender_id: string;
  tender_number: string;
  title: string;
  buyer_name: string;
  state: string;
  category: string;
  estimated_value_inr?: number | null;
  emd_amount_inr?: number | null;
  tender_fee_inr?: number | null;
  processing_fee_inr?: number | null;
  dealing_officer?: string | null;
  org_hierarchy?: string[] | null;
  mandatory_documents?: string[] | null;
  attachments?: Array<{ title: string; file_name: string; url?: string }> | null;
  nit_attachment?: string | null;
  boq_attachment?: string | null;
  tenure_months?: number | null;
  submission_deadline?: string | null;
  portal: string;
  source_url?: string | null;
  status: string;
  has_pdf_document?: boolean;
  extraction?: Record<string, any>;
  rule_pack?: Record<string, any>;
  json_schema?: Record<string, any>;
  preview_details?: Record<string, any>;
}

export interface TenderSearchResponse {
  success: boolean;
  applied_filters?: Record<string, any>;
  total_matches: number;
  page?: number;
  limit?: number;
  source?: string;
  results: TenderItem[];
  error?: string;
}

export interface DocumentItem {
  id: string;
  tender?: string | null;
  file_name: string;
  document_type: string;
  file_size_bytes?: number;
  sha256_hash: string;
  is_digitally_signed?: boolean;
  signature_valid?: boolean;
  is_signature_valid?: boolean;
  signature_details?: {
    signatures?: string[];
    reason?: string;
    [key: string]: any;
  };
  signer_name?: string | null;
  signing_time?: string | null;
  extracted_data?: Record<string, any>;
  uploaded_at?: string;
  created_at?: string;
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const opts: RequestInit = {
    ...options,
    cache: "no-store",
  };

  // 1. Try relative URL (proxied via Next.js rewrites)
  try {
    const res = await fetch(cleanPath, opts);
    return res;
  } catch (networkErr) {
    // 2. If client encounters NetworkError, fallback directly to Django on port 8000
    if (typeof window !== "undefined") {
      try {
        const directUrl = `http://localhost:8000${cleanPath}`;
        const directRes = await fetch(directUrl, opts);
        return directRes;
      } catch (fallbackErr) {
        // Both failed
      }
    }
    throw networkErr;
  }
}

export async function searchTenders(params: {
  q?: string;
  tender_number?: string;
  state?: string;
  category?: string;
  min_value?: number;
  max_value?: number;
  limit?: number;
}): Promise<TenderSearchResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.tender_number) query.set("tender_number", params.tender_number);
  if (params.state && params.state !== "All" && params.state !== "All India") query.set("state", params.state);
  if (params.category && params.category !== "All") query.set("category", params.category);
  if (params.min_value) query.set("min_value", params.min_value.toString());
  if (params.max_value) query.set("max_value", params.max_value.toString());
  if (params.limit) query.set("limit", params.limit.toString());

  const url = `/api/v1/tenders/search/?${query.toString()}`;
  try {
    const res = await apiFetch(url);
    if (!res.ok) {
      throw new Error(`Search failed with status ${res.status}`);
    }
    return await res.json();
  } catch (err: any) {
    console.error("API searchTenders error:", err);
    return {
      success: false,
      total_matches: 0,
      results: [],
      error: err.message || "Failed to connect to TenderBee backend",
    };
  }
}

export async function getTenderDetail(
  identifier: string,
  mode: "skim" | "detailed" = "skim"
): Promise<TenderItem | null> {
  const url = `/api/v1/tenders/${encodeURIComponent(identifier)}/?mode=${mode}`;
  try {
    const res = await apiFetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("API getTenderDetail error:", err);
    return null;
  }
}

export async function uploadTenderPdf(file: File, orgId: string = "org_default"): Promise<{
  success: boolean;
  tender_id?: string;
  rule_pack_id?: string;
  rule_pack?: any;
  extraction?: any;
  error?: string;
}> {
  const formData = new FormData();
  formData.append("pdf_file", file);
  formData.append("org_id", orgId);

  try {
    const res = await apiFetch("/api/v1/tenders/upload-pdf/", {
      method: "POST",
      body: formData,
    });
    return await res.json();
  } catch (err: any) {
    console.error("API uploadTenderPdf error:", err);
    return { success: false, error: err.message || "Upload failed" };
  }
}

export async function intakeTender(
  identifier: string,
  forceRefresh: boolean = false,
  orgId: string = "org_default"
): Promise<{
  success: boolean;
  is_cached?: boolean;
  tender_id?: string;
  tender_number?: string;
  tender_title?: string;
  buyer_name?: string;
  submission_deadline?: string;
  estimated_value_inr?: number;
  emd_amount_inr?: number;
  rule_pack_id?: string;
  rule_pack?: any;
  extraction?: any;
  error?: string;
  reason_code?: string;
}> {
  try {
    const res = await apiFetch("/api/v1/tenders/intake/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identifier,
        force_refresh: forceRefresh,
        org_id: orgId,
      }),
    });
    return await res.json();
  } catch (err: any) {
    console.error("API intakeTender error:", err);
    return { success: false, error: err.message || "Failed to intake tender" };
  }
}

export async function getDocuments(tenderId?: string): Promise<DocumentItem[]> {
  const query = tenderId ? `?tender_id=${encodeURIComponent(tenderId)}` : "";
  try {
    const res = await apiFetch(`/api/v1/documents/${query}`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.results || [];
  } catch (err) {
    console.error("API getDocuments error:", err);
    return [];
  }
}

export async function uploadDocument(
  file: File,
  documentType: string,
  tenderId?: string
): Promise<{ success: boolean; document?: DocumentItem; error?: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  if (tenderId) formData.append("tender_id", tenderId);

  try {
    const res = await apiFetch("/api/v1/documents/upload/", {
      method: "POST",
      body: formData,
    });
    return await res.json();
  } catch (err: any) {
    console.error("API uploadDocument error:", err);
    return { success: false, error: err.message || "Document upload failed" };
  }
}
