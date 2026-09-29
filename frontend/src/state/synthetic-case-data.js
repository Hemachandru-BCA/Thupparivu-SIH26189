/**
 * Central synthetic dataset derived directly from SentinelGraph Final UX Spec.
 * All screens must consume or fall back to this data for 100% consistent storytelling.
 */

export const GLOBAL_CASES = [
  {
    id: 'CASE-0421',
    title: 'Operation Sentinel — Multi-Jurisdiction Syndicate',
    status: 'ACTIVE',
    lead: 'A. Rao',
    role: 'Lead analyst · Editor',
    scope: 'Multi-jurisdiction',
    jurisdictions: ['Federal / Central', 'State / Inter-state', 'Cross-border'],
    snapshot: '26 Sep 2026, 04:58 UTC',
    updated: '26 Sep 2026, 04:58 UTC',
    pipeline: 'JOB-9421',
    pipeline_state: 'running',
    pipeline_stage: 'Stage 5 of 5 · Hypothesis detection running',
    entities_count: 13146,
    communities_count: 695,
    evidence_count: 40292,
    relationships_count: 23982,
    open_findings: 3,
    burst_anomalies: 101,
    draft_dossiers: 42,
    shell_accounts: 3,
    synthetic_notice: 'Synthetic dataset for investigative workbench validation.',
    context: 'Cross-jurisdictional network involving shell commercial entities, layered financial transfers, and suspected unobserved intermediaries spanning Communities 0, 4, 6, and 12.',
    cross_case_links_notice: 'Entities are reused across cases only where deterministic identifiers match. Nothing is linked by name similarity.'
  },
  {
    id: 'CASE-0317',
    title: 'Project Vistara — Hawala Logistics & Trade-Based Layering',
    status: 'ACTIVE',
    lead: 'M. Chen',
    role: 'Senior Investigator',
    scope: 'Regional maritime / customs',
    jurisdictions: ['Customs Zone 3', 'Port Authority'],
    snapshot: '24 Sep 2026, 18:20 UTC',
    updated: '24 Sep 2026, 18:20 UTC',
    pipeline: 'JOB-9380',
    pipeline_state: 'completed',
    pipeline_stage: 'Stage 5 of 5 · Completed',
    entities_count: 4820,
    communities_count: 142,
    evidence_count: 14890,
    relationships_count: 8940,
    open_findings: 1,
    burst_anomalies: 28,
    draft_dossiers: 12,
    shell_accounts: 1,
    synthetic_notice: 'Synthetic dataset for investigative workbench validation.',
    context: 'Trade invoice discrepancies and circular shipping manifestations indicating non-linear value transfers.',
    cross_case_links_notice: 'Entities are reused across cases only where deterministic identifiers match. Nothing is linked by name similarity.'
  },
  {
    id: 'CASE-0198',
    title: 'Operation Bluefin — Digital Asset Gateway Obfuscation',
    status: 'IN REVIEW',
    lead: 'K. Patel',
    role: 'Financial Analyst',
    scope: 'Domestic virtual asset providers',
    jurisdictions: ['Cyber Financial Unit'],
    snapshot: '21 Sep 2026, 11:15 UTC',
    updated: '21 Sep 2026, 11:15 UTC',
    pipeline: 'JOB-9104',
    pipeline_state: 'idle',
    pipeline_stage: 'Stage 5 of 5 · Archived snapshot',
    entities_count: 2190,
    communities_count: 88,
    evidence_count: 7340,
    relationships_count: 4120,
    open_findings: 0,
    burst_anomalies: 9,
    draft_dossiers: 4,
    shell_accounts: 0,
    synthetic_notice: 'Synthetic dataset for investigative workbench validation.',
    context: 'High-frequency transaction bursts across centralized and peer-to-peer OTC desks.',
    cross_case_links_notice: 'Entities are reused across cases only where deterministic identifiers match. Nothing is linked by name similarity.'
  }
];

export const SYNTHETIC_ENTITIES = [
  {
    id: 'ENT-1042',
    name: 'Nicole Jackson',
    type: 'Person',
    community: 'Community 0',
    community_id: 0,
    connections: 184,
    pagerank: 0.018,
    betweenness: 0.092,
    mentions: 48,
    confidence: 'Moderate',
    observed_links: 31,
    inferred_links: 7,
    evidence_records: 18,
    events: 27,
    burst_signals: 4,
    linked_findings: 1,
    rank: '1 of 13,146',
    notes: 'Central coordinator candidate between Community 0 and Community 6.'
  },
  {
    id: 'ENT-1188',
    name: 'Matthew Jones',
    type: 'Person',
    community: 'Community 0',
    community_id: 0,
    connections: 142,
    pagerank: 0.014,
    betweenness: 0.064,
    mentions: 34,
    confidence: 'High',
    observed_links: 26,
    inferred_links: 4,
    evidence_records: 14,
    events: 19,
    burst_signals: 2,
    linked_findings: 1,
    rank: '2 of 13,146',
    notes: 'Direct observed associate of Nicole Jackson; shared communication endpoints.'
  },
  {
    id: 'ENT-2214',
    name: 'Michael Martin',
    type: 'Person',
    community: 'Community 0',
    community_id: 0,
    connections: 129,
    pagerank: 0.012,
    betweenness: 0.058,
    mentions: 29,
    confidence: 'Moderate',
    observed_links: 22,
    inferred_links: 5,
    evidence_records: 11,
    events: 16,
    burst_signals: 1,
    linked_findings: 1,
    rank: '3 of 13,146',
    notes: 'Logistics and cross-border transport facilitator.'
  },
  {
    id: 'ENT-3420',
    name: 'Amanda Frank',
    type: 'Person',
    community: 'Community 0',
    community_id: 0,
    connections: 115,
    pagerank: 0.011,
    betweenness: 0.047,
    mentions: 22,
    confidence: 'Moderate',
    observed_links: 19,
    inferred_links: 3,
    evidence_records: 9,
    events: 12,
    burst_signals: 2,
    linked_findings: 0,
    rank: '4 of 13,146',
    notes: 'Corporate secretarial officer for identified shell entities.'
  },
  {
    id: 'ENT-4811',
    name: 'Carl Khan',
    type: 'Person',
    community: 'Community 6',
    community_id: 6,
    connections: 98,
    pagerank: 0.009,
    betweenness: 0.041,
    mentions: 19,
    confidence: 'Moderate',
    observed_links: 15,
    inferred_links: 6,
    evidence_records: 8,
    events: 11,
    burst_signals: 3,
    linked_findings: 1,
    rank: '5 of 13,146',
    notes: 'Anchor node within Community 6 receiving tiered disbursements.'
  },
  {
    id: 'ENT-5920',
    name: 'Rebecca Mathis',
    type: 'Person',
    community: 'Community 6',
    community_id: 6,
    connections: 84,
    pagerank: 0.008,
    betweenness: 0.035,
    mentions: 16,
    confidence: 'Low',
    observed_links: 12,
    inferred_links: 4,
    evidence_records: 7,
    events: 9,
    burst_signals: 1,
    linked_findings: 0,
    rank: '6 of 13,146',
    notes: 'Associated receiver account signatory.'
  },
  {
    id: 'ENT-6734',
    name: 'John Smith',
    type: 'Person',
    community: 'Community 4',
    community_id: 4,
    connections: 79,
    pagerank: 0.007,
    betweenness: 0.029,
    mentions: 14,
    confidence: 'Moderate',
    observed_links: 11,
    inferred_links: 5,
    evidence_records: 6,
    events: 8,
    burst_signals: 0,
    linked_findings: 1,
    rank: '7 of 13,146',
    notes: 'Financial conduit connecting Community 4 and Community 0.'
  },
  {
    id: 'ENT-7102',
    name: 'Priya Nair',
    type: 'Person',
    community: 'Community 12',
    community_id: 12,
    connections: 68,
    pagerank: 0.006,
    betweenness: 0.024,
    mentions: 12,
    confidence: 'High',
    observed_links: 10,
    inferred_links: 2,
    evidence_records: 6,
    events: 7,
    burst_signals: 1,
    linked_findings: 0,
    rank: '8 of 13,146',
    notes: 'Documented signatory for foreign exchange escrow facility.'
  },
  {
    id: 'ENT-8814',
    name: 'Account 8814',
    type: 'Account',
    community: 'Community 6',
    community_id: 6,
    connections: 54,
    pagerank: 0.005,
    betweenness: 0.021,
    mentions: 26,
    confidence: 'High',
    observed_links: 14,
    inferred_links: 1,
    evidence_records: 12,
    events: 15,
    burst_signals: 5,
    linked_findings: 1,
    rank: '9 of 13,146',
    notes: 'Primary source account for layered multi-hop disbursements.'
  },
  {
    id: 'ENT-0249',
    name: 'Identifier 0249',
    type: 'Identifier',
    community: 'Community 6',
    community_id: 6,
    connections: 46,
    pagerank: 0.004,
    betweenness: 0.019,
    mentions: 18,
    confidence: 'Moderate',
    observed_links: 9,
    inferred_links: 3,
    evidence_records: 8,
    events: 10,
    burst_signals: 2,
    linked_findings: 1,
    rank: '10 of 13,146',
    notes: 'Shared boundary identifier bridging ACC-8814 to downstream accounts.'
  }
];

export const SYNTHETIC_FINDINGS = [
  {
    id: 'FND-003',
    type: 'HIDDEN INTERMEDIARY',
    category: 'Hidden intermediary',
    status: 'Awaiting review',
    confidence: 'Moderate',
    title: 'Potential intermediary bridging communities 0 and 6',
    claim: 'An unobserved intermediary may explain repeated short paths between selected members of communities 0 and 6.',
    supporting_evidence: ['EV-24091', 'EV-22704'],
    counter_evidence: ['EV-19882'],
    unknown: 'No source identifies the intermediary.',
    change_conditions: [
      'Direct source identifying an intermediary',
      'Complete route timestamps across both communities',
      'Independent corroborating evidence record',
      'Resolution of the alternate account path'
    ],
    assessment: {
      band: 'Moderate',
      heuristic_score: '0.64',
      disclaimer: 'Heuristic score, not a probability.',
      components: {
        topology_fit: 'Strong bipartite bottleneck pattern between Nicole Jackson and Carl Khan',
        evidence_support: '2 verified transaction records show timestamp-coupled offsets',
        counter_evidence: '1 direct banking relationship logged in EV-19882 suggests alternate route',
        missing_information: 'No telecommunication intercept or beneficial ownership filing for intermediary'
      }
    },
    suggested_action: 'Perform targeted inquiry on boundary accounts and review EV-19882 provenance.'
  },
  {
    id: 'FND-002',
    type: 'HIDDEN INTERMEDIARY',
    category: 'Hidden intermediary',
    status: 'Awaiting review',
    confidence: 'Moderate',
    title: 'Indirect path around account cluster',
    claim: 'Observed fund routing diverges through synthetic intermediary nodes rather than direct settlement channels.',
    supporting_evidence: ['EV-23817', 'EV-20113'],
    counter_evidence: ['EV-18877'],
    unknown: 'Beneficial ownership of secondary transit account ACC-6712.',
    change_conditions: [
      'Verification of beneficial ownership registry for ACC-6712',
      'Bank statement corroboration for intermediate clearing window'
    ],
    assessment: {
      band: 'Moderate',
      heuristic_score: '0.58',
      disclaimer: 'Heuristic score, not a probability.',
      components: {
        topology_fit: 'Moderate cycle density with bypass edges',
        evidence_support: '2 swift message confirmations',
        counter_evidence: 'Commercial trade justification noted in trade invoice registry',
        missing_information: 'Cross-border clearing documentation'
      }
    },
    suggested_action: 'Request inter-bank ledger reconciliation for ACC-6712.'
  },
  {
    id: 'FND-001',
    type: 'HIDDEN INTERMEDIARY',
    category: 'Hidden intermediary',
    status: 'Awaiting review',
    confidence: 'Low',
    title: 'Sparse connector near observed transfer chain',
    claim: 'Weak structural hole detection between Community 4 and Community 12.',
    supporting_evidence: ['EV-19104'],
    counter_evidence: ['EV-18340', 'EV-17902'],
    unknown: 'Presence of informal value transfer agent.',
    change_conditions: [
      'Direct witness statement or physical surveillance log',
      'Substantial increase in shared identifier density'
    ],
    assessment: {
      band: 'Low',
      heuristic_score: '0.38',
      disclaimer: 'Heuristic score, not a probability.',
      components: {
        topology_fit: 'Weak graph conductance with high path variance',
        evidence_support: 'Single mention in seized mobile device contact list',
        counter_evidence: 'Legitimate business transactions recorded in EV-18340 and EV-17902',
        missing_information: 'Lack of corroborating transfer records'
      }
    },
    suggested_action: 'Retain under passive monitoring; do not escalate until corroborating evidence surfaces.'
  }
];

export const SYNTHETIC_EVIDENCE = [
  {
    id: 'EV-24091',
    title: 'Transaction source record — ACC-8814 to ACC-0249',
    type: 'Transaction source record',
    source: 'Core Banking Ledger Extractor',
    timestamp: '2026-09-26T03:14:22Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-8814', 'ENT-0249', 'ENT-1042'],
    linked_findings: ['FND-003'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Raw CBS dump -> Hash validated -> Stage 3 Parser -> Stage 4 Graph store',
    provenance_details: 'Deterministic transaction trace. Ingested via ISO-20022 parser with verified cryptographic signature.'
  },
  {
    id: 'EV-23817',
    title: 'Account Opening KYC Documentation — Shell Cluster B',
    type: 'Corporate Filing',
    source: 'Registrar of Companies / State Dept',
    timestamp: '2026-09-25T14:48:10Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-3420', 'ENT-8814'],
    linked_findings: ['FND-002'],
    linked_cases: ['CASE-0421', 'CASE-0317'],
    source_lineage: 'Certified true copy provided by financial regulator under statutory notice.',
    provenance_details: 'Includes attested passport scan and utility bill for nominee director.'
  },
  {
    id: 'EV-22704',
    title: 'Wire transfer instruction matching Community 0 & 6 endpoints',
    type: 'Wire Instruction',
    source: 'RTGS / Settlement Gateway',
    timestamp: '2026-09-24T09:12:00Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-1042', 'ENT-4811', 'ENT-0249'],
    linked_findings: ['FND-003'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Automated settlement clearing spool record.',
    provenance_details: 'Direct ledger reference showing matching batch identifier.'
  },
  {
    id: 'EV-20113',
    title: 'Customs Declaration and Manifest Discrepancy Report',
    type: 'Regulatory Notice',
    source: 'Customs Intelligence Wing',
    timestamp: '2026-09-21T16:05:44Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-2214', 'ENT-3420'],
    linked_findings: ['FND-002'],
    linked_cases: ['CASE-0421', 'CASE-0317'],
    source_lineage: 'Formal mutual assistance packet exchange.',
    provenance_details: 'Stamped container movement records with weighbridge variance.'
  },
  {
    id: 'EV-19882',
    title: 'Direct banking relationship registration record (Counter-evidence)',
    type: 'Bank Registry Excerpt',
    source: 'National Banking Authority Registry',
    timestamp: '2026-09-18T10:30:15Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-1042', 'ENT-4811'],
    linked_findings: ['FND-003'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Central account register index search.',
    provenance_details: 'Reflects an explicit direct commercial settlement account relationship, which counters the hypothesis of complete lack of direct connection.'
  },
  {
    id: 'EV-19104',
    title: 'Encrypted Messaging Contact List Extraction',
    type: 'Digital Forensics',
    source: 'State Cyber Forensics Lab',
    timestamp: '2026-09-15T18:22:00Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-6734', 'ENT-7102'],
    linked_findings: ['FND-001'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'UFED physical extraction report hash matched.',
    provenance_details: 'Extracted from mobile hardware seized under judicial warrant.'
  },
  {
    id: 'EV-18877',
    title: 'Invoiced Goods Delivery Confirmation (Counter-evidence)',
    type: 'Commercial Invoice',
    source: 'Logistics Service Provider',
    timestamp: '2026-09-11T12:00:00Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '1a1dc91c907325c69271ddf0c944bc72a1e0b57e7eb18cbd1d0d93be7833a682',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-8814', 'ENT-6712'],
    linked_findings: ['FND-002'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Vendor API automated ingestion.',
    provenance_details: 'Signed consignee receipt matching commercial clearing.'
  },
  {
    id: 'EV-18340',
    title: 'Corporate Registrar Statutory Return for FY25',
    type: 'Statutory Filing',
    source: 'Ministry of Corporate Affairs',
    timestamp: '2026-09-08T08:14:00Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: '254f3b7da7d967fd13f56f1a8e063c483a6503c535ee6f5f9e855523da56ecba',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-7102'],
    linked_findings: ['FND-001'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Official government portal batch export.',
    provenance_details: 'Audited balance sheet indicating standard trading margins.'
  },
  {
    id: 'EV-17902',
    title: 'Foreign Inward Remittance Certificate (FIRC)',
    type: 'Banking Clearance',
    source: 'Authorized Dealer Bank',
    timestamp: '2026-09-02T11:45:12Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: 'c34b6a9a0874c93eb87ee701726a7e0892289c0953a985cc995bb6dbd3a24143',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-7102', 'ENT-6734'],
    linked_findings: ['FND-001'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Bank portal direct electronic filing.',
    provenance_details: 'Verified remittance purpose code indicating software advisory payment.'
  },
  {
    id: 'EV-17411',
    title: 'IP Address Access Log - Online Banking Gateway',
    type: 'Network Telemetry',
    source: 'Financial Security Operations Center',
    timestamp: '2026-08-29T21:10:04Z',
    status: 'Observed',
    verification: 'Hash verified at ingest',
    sha256: 'd8479e0a8761161d1e434f0e5c94bb2e6f3d132646d2994966601b3e8310c144',
    pipeline: 'JOB-9421',
    linked_entities: ['ENT-8814', 'ENT-1042'],
    linked_findings: ['FND-003'],
    linked_cases: ['CASE-0421'],
    source_lineage: 'Syslog collector -> SIEM -> Automated pipeline filter.',
    provenance_details: 'Co-located VPN egress IP used simultaneously for authorization.'
  }
];

export const SYNTHETIC_FUND_TRACE = {
  source_account: 'ACC-8814',
  max_hops: '3 hops',
  min_amount: 'INR 250,000',
  disclaimer: 'This is a graph pattern, not a financial determination.',
  nodes: [
    { id: 'ACC-8814', label: 'ACC-8814', type: 'Observed', role: 'Source account', community: 'Community 6', boundary: false },
    { id: 'ACC-0249', label: 'ACC-0249', type: 'Inferred', role: 'Shared ID intermediary', community: 'Community 6', boundary: true },
    { id: 'ACC-6712', label: 'ACC-6712', type: 'Observed', role: 'Conduit account', community: 'Community 6', boundary: false },
    { id: 'ACC-4420', label: 'ACC-4420', type: 'Inferred', role: 'Terminal sink candidate', community: 'Community 0', boundary: true }
  ],
  transfers: [
    { from: 'ACC-8814', to: 'ACC-0249', amount: 'INR 840,000', type: 'Observed', timestamp: '2026-09-24 10:14 UTC', ref: 'EV-24091' },
    { from: 'ACC-0249', to: 'ACC-6712', amount: 'INR 840,000', type: 'Inferred', timestamp: '2026-09-24 11:05 UTC', ref: 'EV-22704' },
    { from: 'ACC-6712', to: 'ACC-4420', amount: 'INR 310,000', type: 'Observed', timestamp: '2026-09-25 04:30 UTC', ref: 'EV-23817' }
  ]
};

export const SYNTHETIC_TIMELINE = {
  range: '1 Aug 2026 → 26 Sep 2026',
  current_snapshot_index: 9,
  total_snapshots: 12,
  current_snapshot_date: '18 Sep 2026',
  metrics: {
    entities: 12904,
    relationships: 23311,
    communities: 691
  },
  diff: {
    added_entities: 684,
    removed_entities: 19,
    added_relationships: 1204,
    removed_relationships: 87,
    largest_shift: 'Community 6 gained 71 entities'
  },
  events: [
    {
      date: '18 Sep 2026',
      title: 'Batch ingest from State CID & Core Banking Ledger',
      description: 'Added 684 entities; Community 6 expanded by 71 entities around ACC-8814 cluster.',
      entities_delta: '+684',
      rel_delta: '+1,204'
    },
    {
      date: '11 Sep 2026',
      title: 'Customs Declaration Data Ingestion (Batch 04)',
      description: 'Integration of regional trade records and commercial invoice manifests.',
      entities_delta: '+310',
      rel_delta: '+520'
    },
    {
      date: '29 Aug 2026',
      title: 'Initial Case Synthesis & Entity Extraction',
      description: 'First baseline graph generated from seized documents and initial intelligence brief.',
      entities_delta: '+11,910',
      rel_delta: '+21,587'
    }
  ]
};

export const SYNTHETIC_SCENARIO = {
  notice: 'SCENARIO — Simulated result. Removing an entity here is analytical and never changes the case graph.',
  disclaimer: 'Structural only. It says nothing about roles, intent or what a real removal would cause.',
  primary_subject: {
    id: 'ENT-1042',
    name: 'Nicole Jackson',
    role: 'Central coordinator candidate'
  },
  action: 'Remove entity',
  baseline: {
    connected_components: 14,
    largest_component: 12704,
    affected_entities: 0,
    shortest_paths_rerouted: 0
  },
  simulated: {
    connected_components: 19,
    largest_component: 11982,
    affected_entities: 847,
    shortest_paths_rerouted: 63
  },
  most_affected: [
    { id: 'ENT-1188', name: 'Matthew Jones', impact: 'High isolation (path length +3.4)' },
    { id: 'ENT-2214', name: 'Michael Martin', impact: 'Component boundary split' },
    { id: 'ENT-3420', name: 'Amanda Frank', impact: 'Direct neighbor severed' }
  ],
  community_impact: [
    { community: 'Community 0', affected: 214 },
    { community: 'Community 6', affected: 188 }
  ]
};

export const SYNTHETIC_DOSSIER = {
  id: 'DOS-0042',
  finding_ref: 'FND-003',
  case_ref: 'CASE-0421',
  top_warning: 'DRAFT FOR HUMAN REVIEW. Generated sections need analyst validation. Not court-ready. Makes no determination of wrongdoing.',
  approval_status: 'BLOCKED',
  blocking_reasons: [
    'Unresolved finding disposition on FND-003 (still Awaiting review)',
    'Counter-evidence EV-19882 must be explicitly reviewed and acknowledged',
    'Analyst rationale statement required prior to sign-off',
    'Editor role credential verification needed'
  ],
  sections: [
    {
      title: 'Executive summary',
      status: 'Awaiting analyst validation',
      content: 'Synthesized graph topology indicates significant bottleneck conductivity between Community 0 (coordinated by Nicole Jackson ENT-1042) and Community 6 (associated with Carl Khan ENT-4811 and Account 8814). Algorithmic hypothesis FND-003 proposes an unobserved intermediary.'
    },
    {
      title: 'Observed facts',
      status: 'Verified from raw evidence',
      content: '1. Two ledger transfers (EV-24091, EV-22704) show matched offset transfers between ACC-8814 and downstream accounts within 48 hours.\n2. Telemetry record EV-17411 notes concurrent login activity from shared VPN endpoints.\n3. Registry filing EV-19882 confirms an existing direct formal banking arrangement.'
    },
    {
      title: 'Inferred structure',
      status: 'Heuristic model output',
      content: 'Betweenness centrality ranking indicates ENT-1042 ranks 1st in the global component. Path rerouting simulation shows 63 critical paths traversing this structural hole.'
    },
    {
      title: 'Unknowns and gaps',
      status: 'Critical review requirement',
      content: 'No primary identity document or beneficial ownership declaration currently links the intermediary account ACC-0249 to a physical individual.'
    },
    {
      title: 'Evidence references',
      status: 'Prov-indexed',
      content: 'EV-24091, EV-23817, EV-22704, EV-19882, EV-17411'
    },
    {
      title: 'Analyst notes',
      status: 'Draft',
      content: 'Awaiting feedback from Regional Economic Offenses Unit regarding physical verification of nominee director Amanda Frank.'
    }
  ]
};

export const SYNTHETIC_COPILOT_QA = {
  header: {
    case: 'CASE-0421',
    entity: 'Nicole Jackson (ENT-1042)',
    mode: 'Deterministic case queries',
    citations: 'Citations on'
  },
  question: "What evidence supports Nicole Jackson's connection to community 6, and what contradicts the hidden-intermediary finding?",
  answer_label: 'Moderate',
  answer_text: "Based on deterministic case records in CASE-0421:\n\n**Supporting Connection to Community 6:**\n- Record **EV-24091** (Transaction source record) links Nicole Jackson (ENT-1042) to Account 8814 (ENT-8814) via an intermediate transfer sequence.\n- Record **EV-22704** documents wire instructions matching Community 0 and Community 6 routing endpoints.\n- Algorithmic finding **FND-003** posits an unobserved bridging intermediary based on topological path bottlenecks.\n\n**Contradicting / Counter-evidence:**\n- Record **EV-19882** (Direct banking relationship registration record) shows an existing, formally documented banking channel between ENT-1042 and ENT-4811, which directly challenges the claim that an unobserved intermediary is strictly necessary to bridge the clusters.",
  action_trace: [
    { action: 'resolve_case_context', target: 'CASE-0421', result: 'Scope: Multi-jurisdiction (13,146 entities)' },
    { action: 'query_evidence', target: ['EV-24091', 'EV-22704', 'EV-19882'], result: '3 records retrieved with SHA-256 provenance' },
    { action: 'query_findings', target: 'FND-003', result: 'Status: Awaiting review (Moderate heuristic score)' }
  ],
  cited_records: ['EV-24091', 'EV-22704', 'EV-19882', 'FND-003'],
  cited_entities: ['ENT-1042 (Nicole Jackson)', 'ENT-4811 (Carl Khan)', 'ENT-8814 (Account 8814)']
};

export const SYNTHETIC_AUDIT_LOGS = [
  {
    time: '26 Sep 05:04',
    time_iso: '2026-09-26T05:04:12Z',
    actor: 'A. Rao',
    role: 'Lead analyst',
    action: 'COPILOT_QUERY',
    target: 'CASE-0421',
    status: 'Success',
    details: 'Queried evidence basis for Nicole Jackson bridge with citations enabled.'
  },
  {
    time: '26 Sep 05:02',
    time_iso: '2026-09-26T05:02:40Z',
    actor: 'System',
    role: 'Automated Service',
    action: 'FUND_FLOW_TRACE',
    target: 'ACC-8814',
    status: 'Success',
    details: 'Completed 3-hop traversal on minimum threshold INR 250,000.'
  },
  {
    time: '26 Sep 04:58',
    time_iso: '2026-09-26T04:58:19Z',
    actor: 'Model',
    role: 'Inference Engine',
    action: 'HYPOTHESIS_DETECTION',
    target: 'CASE-0421',
    status: 'Success',
    details: 'Identified 3 unobserved intermediary candidates across Community 0 and 6.'
  },
  {
    time: '26 Sep 04:46',
    time_iso: '2026-09-26T04:46:02Z',
    actor: 'A. Rao',
    role: 'Lead analyst',
    action: 'DOSSIER_REVIEW',
    target: 'DOS-0042',
    status: 'Pending',
    details: 'Opened draft review; validation gate flagged pending counter-evidence review.'
  },
  {
    time: '26 Sep 04:42',
    time_iso: '2026-09-26T04:42:30Z',
    actor: 'System',
    role: 'Orchestrator',
    action: 'GRAPH_BUILD',
    target: 'JOB-9421',
    status: 'Success',
    details: 'Indexed 13,146 nodes and 23,982 relationships into graph storage.'
  }
];

export const SYNTHETIC_PIPELINE = {
  job_id: 'JOB-9421',
  case_id: 'CASE-0421',
  retention: 'Retention 7 years · Immutable · Visible to Lead analysts, Auditors',
  stages: [
    { num: 1, name: 'Generate', status: 'Success', duration: '4m 12s', timestamp: '2026-09-26 04:30 UTC' },
    { num: 2, name: 'Preprocess', status: 'Success', duration: '6m 45s', timestamp: '2026-09-26 04:35 UTC' },
    { num: 3, name: 'Extract', status: 'Success', duration: '12m 10s', timestamp: '2026-09-26 04:41 UTC' },
    { num: 4, name: 'Build graph', status: 'Success', duration: '8m 20s', timestamp: '2026-09-26 04:42 UTC' },
    { num: 5, name: 'Hypothesis detection', status: 'Running', duration: 'In progress', timestamp: '2026-09-26 04:58 UTC' }
  ]
};
