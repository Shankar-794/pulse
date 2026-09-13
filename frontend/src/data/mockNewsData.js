/**
 * PULSE NEWS INTELLIGENCE ENGINE
 * FOUNDATION MOCK DATASET
 * 
 * Notice: This is structured mock data adhering to the Pulse Story & Article schemas.
 * In production, this dataset is fetched continuously from the FastAPI backend and
 * backed by PostgreSQL and the deduplication/clustering pipeline.
 */

export const IS_MOCK_DATA = true;

/**
 * @typedef {Object} Article
 * @property {string} id
 * @property {string} title
 * @property {string} description
 * @property {string} url
 * @property {string} author
 * @property {string} published_at
 * @property {string} source_name
 * @property {string} source_domain
 * @property {number} [reliability_score]
 */

/**
 * @typedef {Object} TimelineEvent
 * @property {string} time
 * @property {string} title
 * @property {string} description
 */

/**
 * @typedef {Object} EntityMention
 * @property {string} name
 * @property {'technology' | 'organization' | 'benchmark' | 'concept' | 'vulnerability'} category
 */

/**
 * @typedef {Object} Story
 * @property {string} id
 * @property {string} title
 * @property {string} summary
 * @property {string} why_it_matters
 * @property {'ai' | 'technology' | 'cybersecurity' | 'space' | 'science' | 'business' | 'world'} category
 * @property {string} primary_topic
 * @property {number} importance_score - 0 to 100
 * @property {number} relevance_score - 0 to 100
 * @property {number} freshness_score - 0 to 100
 * @property {number} source_count
 * @property {string} relevance_reason
 * @property {boolean} is_breaking
 * @property {boolean} is_saved
 * @property {string} created_at
 * @property {TimelineEvent[]} timeline
 * @property {EntityMention[]} entities
 * @property {string[]} tags
 * @property {Article[]} articles
 */

export const MOCK_TOPICS = [
  {
    id: "topic-ai",
    name: "Artificial Intelligence",
    slug: "ai",
    category: "ai",
    description: "Foundational models, reasoning systems, autonomous agents, and alignment research.",
    follower_count: 34200,
    is_followed: true
  },
  {
    id: "topic-ml",
    name: "Machine Learning",
    slug: "machine-learning",
    category: "ai",
    description: "Training algorithms, optimization techniques, sparse attention, and synthetic data pipelines.",
    follower_count: 28100,
    is_followed: true
  },
  {
    id: "topic-swe",
    name: "Software Engineering",
    slug: "software-engineering",
    category: "technology",
    description: "Distributed systems, compiler architecture, memory-safe languages, and developer tooling.",
    follower_count: 41800,
    is_followed: true
  },
  {
    id: "topic-cyber",
    name: "Cybersecurity",
    slug: "cybersecurity",
    category: "cybersecurity",
    description: "Zero-day vulnerabilities, threat intelligence, memory safety, and post-quantum cryptography.",
    follower_count: 29500,
    is_followed: true
  },
  {
    id: "topic-cloud",
    name: "Cloud Infrastructure",
    slug: "cloud",
    category: "technology",
    description: "Kubernetes internals, serverless runtimes, multi-region database replication, and edge compute.",
    follower_count: 18200,
    is_followed: false
  },
  {
    id: "topic-robotics",
    name: "Robotics & Embodied AI",
    slug: "robotics",
    category: "technology",
    description: "Humanoid actuation, spatial computing, vision-language-action (VLA) models, and control theory.",
    follower_count: 15900,
    is_followed: false
  },
  {
    id: "topic-space",
    name: "Space Exploration",
    slug: "space",
    category: "space",
    description: "Heavy launch systems, orbital telemetry, astrophysics observations, and deep space probes.",
    follower_count: 22400,
    is_followed: true
  },
  {
    id: "topic-semiconductors",
    name: "Semiconductors & Hardware",
    slug: "semiconductors",
    category: "technology",
    description: "High-NA EUV lithography, GAAFET transistor packaging, optical interconnects, and foundry geopolitics.",
    follower_count: 19700,
    is_followed: true
  },
  {
    id: "topic-startups",
    name: "Venture & Startups",
    slug: "startups",
    category: "business",
    description: "Seed through Series B capital formation, deep-tech spinouts, and founder playbooks.",
    follower_count: 14100,
    is_followed: false
  },
  {
    id: "topic-science",
    name: "Applied Sciences",
    slug: "science",
    category: "science",
    description: "Solid-state materials, room-temperature superconductors, fusion plasma confinement, and genomics.",
    follower_count: 26300,
    is_followed: true
  },
  {
    id: "topic-geopolitics",
    name: "Geopolitics",
    slug: "geopolitics",
    category: "world",
    description: "Strategic export controls, critical mineral choke-points, maritime trade routes, and regulatory treaties.",
    follower_count: 31000,
    is_followed: false
  },
  {
    id: "topic-economics",
    name: "Macroeconomics",
    slug: "economics",
    category: "business",
    description: "Monetary policy, compute energy pricing, semiconductor capital expenditure, and currency liquidity.",
    follower_count: 20800,
    is_followed: false
  }
];

export const MOCK_STORIES = [
  {
    id: "story-001",
    title: "Dual-Phase Reasoning Model Surpasses Human Grandmasters on Code Synthesis Benchmarks",
    summary: "Researchers have released benchmark results for a novel dual-phase reasoning architecture that executes test-time inference tree exploration before code generation. The system achieved 91.4% on SWE-bench Verified and resolved 76% of competitive programming challenges without fine-tuning, demonstrating that latent search at inference time fundamentally shifts automated software engineering capability.",
    why_it_matters: "For software engineering and computer science students, this marks a phase transition from simple autocomplete assistants to autonomous problem-solving engines capable of refactoring complex codebases and catching subtle race conditions.",
    category: "ai",
    primary_topic: "Artificial Intelligence",
    importance_score: 94,
    relevance_score: 98,
    freshness_score: 96,
    source_count: 14,
    is_breaking: true,
    is_saved: false,
    relevance_reason: "High relevance to your AI and Software Engineering student profile.",
    tags: ["AI", "Software Engineering", "Reasoning Models", "SWE-bench", "LLM Inference"],
    created_at: new Date(Date.now() - 80 * 60 * 1000).toISOString(),
    timeline: [
      { time: "08:15 UTC", title: "Paper Preprint Uploaded", description: "ArXiv submission reveals inference compute scaling law scaling curves." },
      { time: "09:30 UTC", title: "SWE-bench Leaderboard Updated", description: "Independent evaluation confirms 91.4% verified score on real-world GitHub issues." },
      { time: "10:45 UTC", title: "Technical Community Reaction", description: "Core maintainers of major open-source repositories validate autonomous patch generation." }
    ],
    entities: [
      { name: "SWE-bench Verified", category: "benchmark" },
      { name: "Tree-of-Thought Search", category: "technology" },
      { name: "OpenAI / Anthropic Research Labs", category: "organization" }
    ],
    articles: [
      {
        id: "art-101",
        title: "Inference Compute Scaling: Why Latent Tree Search Outperforms Pure Parameter Expansion",
        description: "Deep dive into the architectural mechanics of test-time compute versus training-time parameter scaling.",
        url: "https://example.com/research/inference-scaling",
        author: "Dr. Elena Vance",
        published_at: new Date(Date.now() - 75 * 60 * 1000).toISOString(),
        source_name: "MIT Technology Review",
        source_domain: "technologyreview.com",
        reliability_score: 0.96
      },
      {
        id: "art-102",
        title: "Software Engineering Benchmarks Reset as Dual-Phase Agent Smashes Historical Records",
        description: "Analysis of real-world bug fixes submitted autonomously to active repositories.",
        url: "https://example.com/engineering/dual-phase-agent",
        author: "Marcus Thorne",
        published_at: new Date(Date.now() - 105 * 60 * 1000).toISOString(),
        source_name: "ACM Queue",
        source_domain: "queue.acm.org",
        reliability_score: 0.94
      },
      {
        id: "art-103",
        title: "Industry Reaction: The Economic Implications of High-Verification Automated Code Systems",
        description: "Perspectives from principal engineers and venture investors on software productivity.",
        url: "https://example.com/analysis/ai-code-economics",
        author: "Sarah Lin",
        published_at: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
        source_name: "The Information",
        source_domain: "theinformation.com",
        reliability_score: 0.91
      }
    ]
  },
  {
    id: "story-002",
    title: "Critical Zero-Day in Linux eBPF Subsystem Weaponized for Cloud Container Escapes",
    summary: "The Linux Kernel Security Team and CERT have issued emergency advisory CVE-2026-2819 regarding a flaw in the Extended Berkeley Packet Filter (eBPF) verifier logic. Exploitation permits an unprivileged local user inside a standard container to bypass namespace barriers and execute arbitrary root-level ring-0 kernel code on host hypervisors.",
    why_it_matters: "Immediate mitigation required for any developer running multi-tenant Kubernetes clusters or bare-metal development servers. It illustrates the security trade-offs between kernel observability and attack surface enlargement.",
    category: "cybersecurity",
    primary_topic: "Cybersecurity",
    importance_score: 96,
    relevance_score: 92,
    freshness_score: 98,
    source_count: 19,
    is_breaking: true,
    is_saved: false,
    relevance_reason: "Direct impact on your Cloud Infrastructure and Operating Systems security coursework.",
    tags: ["Cybersecurity", "Linux Kernel", "eBPF", "Vulnerability", "Kubernetes", "CVE-2026-2819"],
    created_at: new Date(Date.now() - 165 * 60 * 1000).toISOString(),
    timeline: [
      { time: "06:00 UTC", title: "CVE-2026-2819 Published", description: "Advisory assigned CVSS score 9.8 (Critical)." },
      { time: "07:20 UTC", title: "Kernel Patch Backported", description: "Stable trees 6.6 LTS, 6.12 LTS, and 6.14 release immediate point revisions." },
      { time: "08:50 UTC", title: "Major Cloud Providers Roll Hot-Patches", description: "AWS, GCP, and Azure deploy live-patch hypervisor mitigations without node reboot." }
    ],
    entities: [
      { name: "CVE-2026-2819", category: "vulnerability" },
      { name: "Linux Kernel Verifier", category: "technology" },
      { name: "Kubernetes / OCI Containers", category: "technology" },
      { name: "CISA / CERT", category: "organization" }
    ],
    articles: [
      {
        id: "art-201",
        title: "Urgent Advisory: Kernel Verifier Logic Hole Exposes Container Hosts to Arbitrary Code Execution",
        description: "Technical breakdown of the register state truncation bug in eBPF verification path.",
        url: "https://example.com/security/ebpf-cve-2026-2819",
        author: "Kees Cook",
        published_at: new Date(Date.now() - 150 * 60 * 1000).toISOString(),
        source_name: "LWN.net",
        source_domain: "lwn.net",
        reliability_score: 0.98
      },
      {
        id: "art-202",
        title: "Cloud Infrastructure Scrambles to Patch Critical Container Breakout Flaw",
        description: "Enterprise cloud response and zero-downtime live patching verification.",
        url: "https://example.com/security/container-breakout",
        author: "Dan Goodin",
        published_at: new Date(Date.now() - 180 * 60 * 1000).toISOString(),
        source_name: "Ars Technica",
        source_domain: "arstechnica.com",
        reliability_score: 0.93
      }
    ]
  },
  {
    id: "story-003",
    title: "TSMC Reports 78% Defect-Free Yield on 2nm GAAFET Nodes Ahead of 2026 Production Window",
    summary: "Taiwan Semiconductor Manufacturing Company (TSMC) confirmed during its quarterly technology symposium that trial production runs for its N2 (2-nanometer class) process utilizing Gate-All-Around nanosheet transistors have reached an industry-leading 78% defect-free yield. High-volume manufacturing is now confirmed to begin in H1 2026.",
    why_it_matters: "N2 represents the industry's shift away from FinFET architectures to nanosheets, providing a 15% speed increase at identical power or a 30% power reduction. Essential for mobile processors and next-gen AI inference clusters.",
    category: "technology",
    primary_topic: "Semiconductors & Hardware",
    importance_score: 88,
    relevance_score: 90,
    freshness_score: 90,
    source_count: 11,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "High relevance to your Hardware Architecture and Semiconductor interests.",
    tags: ["Semiconductors", "TSMC", "GAAFET", "Hardware", "Nanosheets", "2nm"],
    created_at: new Date(Date.now() - 250 * 60 * 1000).toISOString(),
    timeline: [
      { time: "03:00 UTC", title: "TSMC Symposium Keynote", description: "CTO discloses N2 trial wafer metrics from Fab 20 in Hsinchu." },
      { time: "04:30 UTC", title: "Equipment Supply Update", description: "ASML confirms delivery of High-NA EUV lithography systems to Hsinchu test lines." }
    ],
    entities: [
      { name: "TSMC", category: "organization" },
      { name: "ASML", category: "organization" },
      { name: "GAAFET Nanosheet", category: "technology" }
    ],
    articles: [
      {
        id: "art-301",
        title: "TSMC 2nm GAAFET Wafer Yield Exceeds Internal Milestones at Fab 20",
        description: "In-depth silicon analysis of nanosheet capacitance and leakage improvements.",
        url: "https://example.com/hardware/tsmc-2nm-yield",
        author: "Anton Shilov",
        published_at: new Date(Date.now() - 240 * 60 * 1000).toISOString(),
        source_name: "AnandTech",
        source_domain: "anandtech.com",
        reliability_score: 0.95
      }
    ]
  },
  {
    id: "story-004",
    title: "ESA Juice Spacecraft Executes Unprecedented Double Gravity Assist Around Moon and Earth",
    summary: "The European Space Agency's Jupiter Icy Moons Explorer (Juice) has completed a world-first Lunar-Earth gravity assist maneuver, skimming just 750 kilometers above the lunar crater surface before swinging past Earth 36 hours later. The maneuver shaved 3.2 km/s of velocity requirement and saved 150 kg of onboard propellant for its 2031 orbital insertion around Ganymede.",
    why_it_matters: "Demonstrates precision orbital mechanics and deep-space trajectory optimization under non-linear gravitational perturbations, preserving valuable scientific mission lifetime.",
    category: "space",
    primary_topic: "Space Exploration",
    importance_score: 82,
    relevance_score: 86,
    freshness_score: 85,
    source_count: 8,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "Matches your Space Exploration and Physics tracking filters.",
    tags: ["Space", "ESA", "Juice Probe", "Orbital Mechanics", "Astrophysics"],
    created_at: new Date(Date.now() - 360 * 60 * 1000).toISOString(),
    timeline: [
      { time: "Yesterday", title: "Lunar Closest Approach", description: "Juice passed within 750 km of the lunar south pole." },
      { time: "02:15 UTC", title: "Perigee Earth Flyby", description: "Atmospheric telemetry verified exact delta-v insertion vector." }
    ],
    entities: [
      { name: "Juice Spacecraft", category: "technology" },
      { name: "European Space Agency", category: "organization" },
      { name: "Ganymede", category: "concept" }
    ],
    articles: [
      {
        id: "art-401",
        title: "Braking via Moon and Earth: How Juice Pulled Off an Orbital Mechanics Miracle",
        description: "Flight dynamics telemetry review from ESOC Darmstadt control center.",
        url: "https://example.com/space/juice-double-flyby",
        author: "Jonathan Amos",
        published_at: new Date(Date.now() - 345 * 60 * 1000).toISOString(),
        source_name: "BBC Science",
        source_domain: "bbc.co.uk",
        reliability_score: 0.92
      }
    ]
  },
  {
    id: "story-005",
    title: "Department of Justice Proposes Unbundling Framework for Cloud Hyperscaler Compute Stacks",
    summary: "The US Department of Justice Antitrust Division has filed an amicus brief proposing structural separation between proprietary cloud virtualization infrastructure, GPU allocation queues, and high-level developer software suites. The filing argues that exclusive compute agreements stifle independent AI startup competition.",
    why_it_matters: "If adopted into federal regulatory frameworks, developers and independent startups could access enterprise-grade GPU clusters without mandatory lock-in to proprietary cloud runtime ecosystems.",
    category: "business",
    primary_topic: "Macroeconomics",
    importance_score: 84,
    relevance_score: 78,
    freshness_score: 80,
    source_count: 16,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "Impacts cloud hosting costs, AI startup viability, and software economics.",
    tags: ["Business", "Antitrust", "Cloud Compute", "GPU Allocation", "DOJ"],
    created_at: new Date(Date.now() - 450 * 60 * 1000).toISOString(),
    timeline: [
      { time: "14:00 UTC", title: "Legal Brief Lodged", description: "Federal court in Washington receives 84-page competitive assessment." },
      { time: "16:20 UTC", title: "Hyperscaler Consortium Responds", description: "Industry trade association issues statement asserting integrated efficiencies." }
    ],
    entities: [
      { name: "US Department of Justice", category: "organization" },
      { name: "Cloud Computing Infrastructure", category: "technology" }
    ],
    articles: [
      {
        id: "art-501",
        title: "DOJ Takes Aim at GPU Tier Bundling in Landmark Tech Competition Filing",
        description: "Analysis of legal precedents and potential remedies for artificial compute scarcity.",
        url: "https://example.com/policy/cloud-antitrust-filing",
        author: "David McCabe",
        published_at: new Date(Date.now() - 420 * 60 * 1000).toISOString(),
        source_name: "The Wall Street Journal",
        source_domain: "wsj.com",
        reliability_score: 0.93
      }
    ]
  },
  {
    id: "story-006",
    title: "Solid-State Lithium-Metal Anode Cells Pass 1,200 Fast-Charge Cycles with 92% Capacity Retention",
    summary: "Materials science researchers in collaboration with QuantumScape and national laboratories have verified third-party endurance test results for an anodeless lithium-metal solid-state battery. The cells completed 1,200 continuous 15-minute 4C fast-charge cycles at room temperature while preserving 92% initial volumetric energy density.",
    why_it_matters: "Overcomes the decades-long dendrite short-circuit failure mode in lithium-metal anodes. Paves the way for electric vehicles with 500-mile real-world ranges and sub-15-minute charging without thermal runaway risk.",
    category: "science",
    primary_topic: "Applied Sciences",
    importance_score: 86,
    relevance_score: 84,
    freshness_score: 88,
    source_count: 10,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "High interest in energy storage materials science and clean tech engineering.",
    tags: ["Science", "Batteries", "Solid-State", "Materials Engineering", "Energy"],
    created_at: new Date(Date.now() - 495 * 60 * 1000).toISOString(),
    timeline: [
      { time: "Yesterday", title: "Peer-Reviewed Study in Nature Materials", description: "Synchrotron X-ray imaging confirms absence of dendritic voids during fast charging." },
      { time: "06:00 UTC", title: "Pilot Manufacturing Scaleup", description: "Contract manufacturer announces automated roll-to-roll separator coating facility." }
    ],
    entities: [
      { name: "QuantumScape / National Labs", category: "organization" },
      { name: "Ceramic Solid-State Separator", category: "technology" },
      { name: "Nature Materials", category: "organization" }
    ],
    articles: [
      {
        id: "art-601",
        title: "Lithium-Metal Solid State Reaches Automotive Durability Benchmark",
        description: "Experimental verification of ceramic-polymer hybrid separator performance.",
        url: "https://example.com/energy/solid-state-breakthrough",
        author: "Dr. Aris Thorne",
        published_at: new Date(Date.now() - 480 * 60 * 1000).toISOString(),
        source_name: "Nature Energy",
        source_domain: "nature.com",
        reliability_score: 0.97
      }
    ]
  },
  {
    id: "story-007",
    title: "NIST and CISA Mandate Post-Quantum Cryptography Migration Roadmaps for Critical Banking",
    summary: "The National Institute of Standards and Technology (NIST) alongside CISA has issued an enforceable directive establishing 2028 as the formal cutoff for legacy RSA-2048 and ECC public key infrastructure across federally regulated banking institutions. Systems must transition to ML-KEM (Kyber) and ML-DSA (Dilithium) post-quantum algorithms.",
    why_it_matters: "Addresses the 'Harvest Now, Decrypt Later' threat vector. Software engineers will see massive rewrites across TLS stacks, authentication tokens, hardware security modules (HSMs), and cryptographic libraries.",
    category: "cybersecurity",
    primary_topic: "Cybersecurity",
    importance_score: 89,
    relevance_score: 93,
    freshness_score: 86,
    source_count: 15,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "Directly impacts security protocols, cryptographic implementations, and backend engineering.",
    tags: ["Cybersecurity", "Post-Quantum", "Cryptography", "NIST", "ML-KEM", "Kyber"],
    created_at: new Date(Date.now() - 600 * 60 * 1000).toISOString(),
    timeline: [
      { time: "Two Days Ago", title: "Final Standards Published", description: "FIPS 203, 204, and 205 formalized for global implementation." },
      { time: "09:00 UTC", title: "Regulatory Mandate Issued", description: "Federal Financial Institutions Examination Council publishes compliance timetable." }
    ],
    entities: [
      { name: "NIST", category: "organization" },
      { name: "CISA", category: "organization" },
      { name: "ML-KEM (CRYSTALS-Kyber)", category: "technology" }
    ],
    articles: [
      {
        id: "art-701",
        title: "Banking Core Systems Face Mandatory Post-Quantum Upgrade Timeline",
        description: "How financial legacy systems plan to replace RSA key exchanges with lattice-based cryptography.",
        url: "https://example.com/infosec/pqc-banking-mandate",
        author: "Lily Hay Newman",
        published_at: new Date(Date.now() - 570 * 60 * 1000).toISOString(),
        source_name: "Wired Security",
        source_domain: "wired.com",
        reliability_score: 0.92
      }
    ]
  },
  {
    id: "story-008",
    title: "European Union AI Act Board Releases Standardized Watermarking and Audit Protocol",
    summary: "The European AI Office has finalized its Technical Implementation Guidance on synthetic content provenance under Articles 50 and 52 of the EU AI Act. Commercial model providers must embed cryptographically verifiable C2PA metadata and latent watermarking resistant to re-encoding across all generated text, audio, and visual outputs.",
    why_it_matters: "Enforces global architectural requirements on generative AI APIs and model serving frameworks operating in European jurisdictions, impacting model inference latency and client verification tooling.",
    category: "world",
    primary_topic: "Geopolitics",
    importance_score: 87,
    relevance_score: 81,
    freshness_score: 82,
    source_count: 17,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "High relevance to regulatory frameworks governing software and AI deployments.",
    tags: ["World", "EU AI Act", "Provenance", "C2PA", "AI Regulation", "Compliance"],
    created_at: new Date(Date.now() - 720 * 60 * 1000).toISOString(),
    timeline: [
      { time: "07:30 UTC", title: "Draft Annex Finalized", description: "Article 50 implementation details ratified by member state delegates." },
      { time: "11:00 UTC", title: "API Specification Open-Sourced", description: "Reference C2PA manifest verification library published under Apache 2.0." }
    ],
    entities: [
      { name: "European AI Office", category: "organization" },
      { name: "C2PA Coalition", category: "organization" },
      { name: "EU AI Act", category: "concept" }
    ],
    articles: [
      {
        id: "art-801",
        title: "EU Standardizes Watermarking Requirements for Generative AI Pipelines",
        description: "Technical analysis of how C2PA content credentials will be verified at web scale.",
        url: "https://example.com/tech-policy/eu-ai-watermarking",
        author: "Javier Espinoza",
        published_at: new Date(Date.now() - 690 * 60 * 1000).toISOString(),
        source_name: "Financial Times",
        source_domain: "ft.com",
        reliability_score: 0.94
      }
    ]
  },
  {
    id: "story-009",
    title: "Neutral-Atom Quantum Processor Demonstrates Fault-Tolerant Logical Qubit Gate Array",
    summary: "Harvard, QuEra Computing, and MIT researchers have demonstrated two-qubit entangling gates across 48 fault-tolerant logical qubits using optical tweezers in a 3D neutral-atom architecture. By utilizing 3D toric surface codes, the error rate per logical operation dropped below physical qubit noise thresholds for the first time.",
    why_it_matters: "A critical experimental verification that quantum error correction works in practice, bringing commercially viable fault-tolerant quantum algorithms significantly closer than previously forecasted.",
    category: "science",
    primary_topic: "Applied Sciences",
    importance_score: 91,
    relevance_score: 88,
    freshness_score: 80,
    source_count: 12,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "Matches your Quantum Computing and Physics exploration preferences.",
    tags: ["Science", "Quantum Computing", "Logical Qubits", "Neutral Atoms", "Error Correction"],
    created_at: new Date(Date.now() - 840 * 60 * 1000).toISOString(),
    timeline: [
      { time: "Yesterday", title: "Nature Physics Cover Article", description: "Experimental verification of 48 transversal logical CZ gates." },
      { time: "12:00 UTC", title: "Architecture Roadmap Update", description: "Consortium outlines commercial 10,000-physical-atom system for 2027." }
    ],
    entities: [
      { name: "QuEra Computing", category: "organization" },
      { name: "Harvard Quantum Initiative", category: "organization" },
      { name: "Neutral-Atom Array", category: "technology" }
    ],
    articles: [
      {
        id: "art-901",
        title: "Error-Corrected Quantum Computing Crosses the Break-Even Threshold",
        description: "In-depth physics breakdown of Rydberg atom array interaction and gate fidelity.",
        url: "https://example.com/quantum/fault-tolerant-neutral-atoms",
        author: "Dr. Sophia Hayes",
        published_at: new Date(Date.now() - 810 * 60 * 1000).toISOString(),
        source_name: "Quanta Magazine",
        source_domain: "quantamagazine.org",
        reliability_score: 0.96
      }
    ]
  },
  {
    id: "story-010",
    title: "DARPA AIxCC Finals Reveal Autonomous Agents Capable of Discovering and Patching Zero-Days in 15 Minutes",
    summary: "The Artificial Intelligence Cyber Challenge (AIxCC) finals concluded with top autonomous cyber-reasoning systems (CRSs) demonstrating zero-human-in-the-loop vulnerability remediation. The leading agent autonomously discovered a memory corruption bug in an open-source web server, synthesized a proof-of-concept exploit, wrote a patch that passed 100% of regression tests, and deployed it within 14 minutes.",
    why_it_matters: "Direct preview of the future of automated defense vs. offensive operations in software systems. It radically changes the economics of zero-day discovery and patch management.",
    category: "cybersecurity",
    primary_topic: "Cybersecurity",
    importance_score: 93,
    relevance_score: 95,
    freshness_score: 79,
    source_count: 13,
    is_breaking: false,
    is_saved: false,
    relevance_reason: "High relevance to your Cybersecurity and Automated Software Engineering interests.",
    tags: ["Cybersecurity", "AIxCC", "Autonomous Defense", "Zero-Day", "DARPA"],
    created_at: new Date(Date.now() - 960 * 60 * 1000).toISOString(),
    timeline: [
      { time: "Yesterday", title: "Finals Competition Round", description: "Synthetic multi-tier challenges evaluated under strict sandboxes." },
      { time: "15:00 UTC", title: "DARPA Awards Announced", description: "Top prize awarded to hybrid symbolic-execution and LLM reasoning agent." }
    ],
    entities: [
      { name: "DARPA", category: "organization" },
      { name: "AIxCC Challenge", category: "benchmark" },
      { name: "Cyber Reasoning Systems (CRS)", category: "technology" }
    ],
    articles: [
      {
        id: "art-1001",
        title: "Autonomous Software Defense Comes of Age at DARPA AIxCC Finals",
        description: "How autonomous agents combine static analysis with neural reasoning to patch bugs safely.",
        url: "https://example.com/security/darpa-aixcc-finals",
        author: "Kim Zetter",
        published_at: new Date(Date.now() - 945 * 60 * 1000).toISOString(),
        source_name: "Dark Reading",
        source_domain: "darkreading.com",
        reliability_score: 0.91
      }
    ]
  }
];

export const DEFAULT_USER_PREFERENCES = {
  interests: [
    "AI",
    "Software Engineering",
    "Cybersecurity",
    "Semiconductors",
    "Space",
    "Science"
  ],
  breaking_sensitivity: "standard",
  importance_threshold: 50,
  preferred_sources: [
    "MIT Technology Review",
    "LWN.net",
    "Ars Technica",
    "AnandTech",
    "Quanta Magazine",
    "ACM Queue"
  ],
  hidden_topics: [],
  theme: "terminal-dark"
};
