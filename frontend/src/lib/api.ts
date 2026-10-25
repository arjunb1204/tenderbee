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
    if (res.status >= 500 && typeof window !== "undefined") {
      try {
        const directUrl = `http://localhost:8000${cleanPath}`;
        const directRes = await fetch(directUrl, opts);
        if (directRes.ok) return directRes;
      } catch (e) {
        // Fallback failed, return original proxy response
      }
    }
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

export interface PortalRegistryItem {
  name: string;
  code: string;
  type: string; // "State" | "Union Territory" | "Central" | "Aggregator"
  portal_name: string;
  domain: string;
  url: string;
  engine: string;
}

export interface PortalRegistryResponse {
  success: boolean;
  total: number;
  portals: PortalRegistryItem[];
}

export const ALL_STATE_PORTALS: PortalRegistryItem[] = [
  // 28 States
  { name: "Andhra Pradesh", code: "AP", type: "State", portal_name: "Andhra Pradesh eProcurement Portal", domain: "tender.apeprocurement.gov.in", url: "https://tender.apeprocurement.gov.in", engine: "e-Procure" },
  { name: "Arunachal Pradesh", code: "AR", type: "State", portal_name: "Arunachal Pradesh e-Procurement Portal", domain: "arunachaltenders.gov.in", url: "https://arunachaltenders.gov.in", engine: "GePNIC" },
  { name: "Assam", code: "AS", type: "State", portal_name: "Assam Tenders e-Procurement System", domain: "assamtenders.gov.in", url: "https://assamtenders.gov.in", engine: "GePNIC" },
  { name: "Bihar", code: "BR", type: "State", portal_name: "Bihar eProc2 Portal", domain: "eproc2.bihar.gov.in", url: "https://eproc2.bihar.gov.in", engine: "NextGen eProc" },
  { name: "Chhattisgarh", code: "CG", type: "State", portal_name: "Chhattisgarh e-Procurement System", domain: "eproc.cgstate.gov.in", url: "https://eproc.cgstate.gov.in", engine: "e-Procure" },
  { name: "Goa", code: "GA", type: "State", portal_name: "Goa e-Procurement Portal", domain: "eprocure.goa.gov.in", url: "https://eprocure.goa.gov.in", engine: "GePNIC" },
  { name: "Gujarat", code: "GJ", type: "State", portal_name: "Gujarat nProcure e-Tendering", domain: "tender.nprocure.com", url: "https://tender.nprocure.com", engine: "nProcure" },
  { name: "Haryana", code: "HR", type: "State", portal_name: "Haryana e-Procurement Portal", domain: "etenders.hry.nic.in", url: "https://etenders.hry.nic.in", engine: "GePNIC" },
  { name: "Himachal Pradesh", code: "HP", type: "State", portal_name: "Himachal Pradesh Tenders Portal", domain: "hptenders.gov.in", url: "https://hptenders.gov.in", engine: "GePNIC" },
  { name: "Jharkhand", code: "JH", type: "State", portal_name: "Jharkhand Tenders e-Procurement System", domain: "jharkhandtenders.gov.in", url: "https://jharkhandtenders.gov.in", engine: "GePNIC" },
  { name: "Karnataka", code: "KA", type: "State", portal_name: "Karnataka Public Procurement Portal (KPPP)", domain: "kppp.karnataka.gov.in", url: "https://kppp.karnataka.gov.in", engine: "KPPP" },
  { name: "Kerala", code: "KL", type: "State", portal_name: "Kerala e-Tenders Portal", domain: "etenders.kerala.gov.in", url: "https://etenders.kerala.gov.in", engine: "GePNIC" },
  { name: "Madhya Pradesh", code: "MP", type: "State", portal_name: "MP Tenders Portal", domain: "mptenders.gov.in", url: "https://mptenders.gov.in", engine: "GePNIC" },
  { name: "Maharashtra", code: "MH", type: "State", portal_name: "MahaTenders (Maharashtra e-Procurement)", domain: "mahatenders.gov.in", url: "https://mahatenders.gov.in", engine: "GePNIC" },
  { name: "Manipur", code: "MN", type: "State", portal_name: "Manipur e-Procurement Portal", domain: "manipurtenders.gov.in", url: "https://manipurtenders.gov.in", engine: "GePNIC" },
  { name: "Meghalaya", code: "ML", type: "State", portal_name: "Meghalaya Tenders Portal", domain: "meghalayatenders.gov.in", url: "https://meghalayatenders.gov.in", engine: "GePNIC" },
  { name: "Mizoram", code: "MZ", type: "State", portal_name: "Mizoram e-Procurement System", domain: "mizoramtenders.gov.in", url: "https://mizoramtenders.gov.in", engine: "GePNIC" },
  { name: "Nagaland", code: "NL", type: "State", portal_name: "Nagaland e-Procurement Portal", domain: "nagalandtenders.gov.in", url: "https://nagalandtenders.gov.in", engine: "GePNIC" },
  { name: "Odisha", code: "OD", type: "State", portal_name: "Tenders Odisha Portal", domain: "tendersodisha.gov.in", url: "https://tendersodisha.gov.in", engine: "GePNIC" },
  { name: "Punjab", code: "PB", type: "State", portal_name: "Punjab e-Procurement Portal", domain: "eproc.punjab.gov.in", url: "https://eproc.punjab.gov.in", engine: "GePNIC" },
  { name: "Rajasthan", code: "RJ", type: "State", portal_name: "Rajasthan e-Procurement System", domain: "eproc.rajasthan.gov.in", url: "https://eproc.rajasthan.gov.in", engine: "GePNIC" },
  { name: "Sikkim", code: "SK", type: "State", portal_name: "Sikkim Tenders Portal", domain: "sikkimtender.gov.in", url: "https://sikkimtender.gov.in", engine: "GePNIC" },
  { name: "Tamil Nadu", code: "TN", type: "State", portal_name: "Tamil Nadu e-Tenders Portal", domain: "tntenders.gov.in", url: "https://tntenders.gov.in", engine: "GePNIC" },
  { name: "Telangana", code: "TS", type: "State", portal_name: "Telangana e-Procurement Portal", domain: "tender.telangana.gov.in", url: "https://tender.telangana.gov.in", engine: "e-Procure" },
  { name: "Tripura", code: "TR", type: "State", portal_name: "Tripura Tenders Portal", domain: "tripuratenders.gov.in", url: "https://tripuratenders.gov.in", engine: "GePNIC" },
  { name: "Uttar Pradesh", code: "UP", type: "State", portal_name: "e-Tender Uttar Pradesh", domain: "etender.up.nic.in", url: "https://etender.up.nic.in", engine: "GePNIC" },
  { name: "Uttarakhand", code: "UK", type: "State", portal_name: "Uttarakhand Tenders Portal", domain: "uktenders.gov.in", url: "https://uktenders.gov.in", engine: "GePNIC" },
  { name: "West Bengal", code: "WB", type: "State", portal_name: "West Bengal Tenders (WBTenders)", domain: "wbtenders.gov.in", url: "https://wbtenders.gov.in", engine: "GePNIC" },
  // 8 Union Territories
  { name: "Andaman and Nicobar Islands", code: "AN", type: "Union Territory", portal_name: "Andaman & Nicobar eProcurement", domain: "eprocure.andaman.gov.in", url: "https://eprocure.andaman.gov.in", engine: "GePNIC" },
  { name: "Chandigarh", code: "CH", type: "Union Territory", portal_name: "Chandigarh Administration eTenders", domain: "etenders.chd.nic.in", url: "https://etenders.chd.nic.in", engine: "GePNIC" },
  { name: "Dadra and Nagar Haveli and Daman and Diu", code: "DD", type: "Union Territory", portal_name: "Daman & Diu / DNH e-Tenders", domain: "ddtenders.gov.in", url: "https://ddtenders.gov.in", engine: "GePNIC" },
  { name: "Delhi", code: "DL", type: "Union Territory", portal_name: "Delhi Govt e-Procurement System", domain: "govtprocurement.delhi.gov.in", url: "https://govtprocurement.delhi.gov.in", engine: "GePNIC" },
  { name: "Jammu and Kashmir", code: "JK", type: "Union Territory", portal_name: "JK Tenders Portal", domain: "jktenders.gov.in", url: "https://jktenders.gov.in", engine: "GePNIC" },
  { name: "Ladakh", code: "LA", type: "Union Territory", portal_name: "Ladakh Procurement Portal (CPPP)", domain: "eprocure.gov.in", url: "https://eprocure.gov.in", engine: "GePNIC" },
  { name: "Lakshadweep", code: "LD", type: "Union Territory", portal_name: "Lakshadweep Procurement (CPPP)", domain: "eprocure.gov.in", url: "https://eprocure.gov.in", engine: "GePNIC" },
  { name: "Puducherry", code: "PY", type: "Union Territory", portal_name: "Puducherry e-Tenders Portal", domain: "pudutenders.gov.in", url: "https://pudutenders.gov.in", engine: "GePNIC" },
  // Central / National
  { name: "Central Government (CPPP)", code: "CENTRAL", type: "Central", portal_name: "Central Public Procurement Portal", domain: "eprocure.gov.in", url: "https://eprocure.gov.in", engine: "GePNIC" },
  { name: "GeM", code: "GEM", type: "Central", portal_name: "Government e-Marketplace", domain: "gem.gov.in", url: "https://gem.gov.in", engine: "GeM" },
  { name: "Indian Railways (IREPS)", code: "RAIL", type: "Central", portal_name: "Indian Railways E-Procurement System", domain: "ireps.gov.in", url: "https://ireps.gov.in", engine: "IREPS" },
  { name: "Defence Procurement", code: "DEF", type: "Central", portal_name: "Defence e-Procurement Portal", domain: "defproc.gov.in", url: "https://defproc.gov.in", engine: "GePNIC" },
  { name: "Infralens", code: "INFRA", type: "Aggregator", portal_name: "Infralens Tender Mirror", domain: "tenders.infralens.in", url: "https://tenders.infralens.in", engine: "Mirror" },
];

export async function getPortals(params?: { type?: string; q?: string }): Promise<PortalRegistryResponse> {
  const query = new URLSearchParams();
  if (params?.type) query.set("type", params.type);
  if (params?.q) query.set("q", params.q);

  const url = `/api/v1/tenders/portals/?${query.toString()}`;
  try {
    const res = await apiFetch(url);
    if (!res.ok) throw new Error(`Portal registry request failed (${res.status})`);
    return await res.json();
  } catch (err: any) {
    console.warn("getPortals API fallback:", err);
    let filtered = ALL_STATE_PORTALS;
    if (params?.type) {
      filtered = filtered.filter((p) => p.type.toLowerCase() === params.type?.toLowerCase());
    }
    if (params?.q) {
      const q = params.q.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.domain.toLowerCase().includes(q) ||
          p.code.toLowerCase().includes(q) ||
          p.portal_name.toLowerCase().includes(q)
      );
    }
    return {
      success: true,
      total: filtered.length,
      portals: filtered,
    };
  }
}

