"""
News Service for Pulse Foundation.
Provides structured, realistic intelligence data conforming to Pydantic schemas.
All data is clearly marked as demonstration/mock intelligence data, ready to be
swapped with PostgreSQL database queries in subsequent milestones.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# Clear indicator marking foundational mock dataset
IS_MOCK_DATA = True

MOCK_TOPICS = [
    {
        "id": "topic-ai",
        "name": "Artificial Intelligence",
        "slug": "ai",
        "category": "ai",
        "description": "Foundational models, reasoning systems, autonomous agents, and alignment research.",
        "follower_count": 34200,
        "is_followed": True
    },
    {
        "id": "topic-ml",
        "name": "Machine Learning",
        "slug": "machine-learning",
        "category": "ai",
        "description": "Training algorithms, optimization techniques, sparse attention, and synthetic data pipelines.",
        "follower_count": 28100,
        "is_followed": True
    },
    {
        "id": "topic-swe",
        "name": "Software Engineering",
        "slug": "software-engineering",
        "category": "technology",
        "description": "Distributed systems, compiler architecture, memory-safe languages, and developer tooling.",
        "follower_count": 41800,
        "is_followed": True
    },
    {
        "id": "topic-cyber",
        "name": "Cybersecurity",
        "slug": "cybersecurity",
        "category": "cybersecurity",
        "description": "Zero-day vulnerabilities, threat intelligence, memory safety, and post-quantum cryptography.",
        "follower_count": 29500,
        "is_followed": True
    },
    {
        "id": "topic-cloud",
        "name": "Cloud Infrastructure",
        "slug": "cloud",
        "category": "technology",
        "description": "Kubernetes internals, serverless runtimes, multi-region database replication, and edge compute.",
        "follower_count": 18200,
        "is_followed": False
    },
    {
        "id": "topic-robotics",
        "name": "Robotics & Embodied AI",
        "slug": "robotics",
        "category": "technology",
        "description": "Humanoid actuation, spatial computing, vision-language-action (VLA) models, and control theory.",
        "follower_count": 15900,
        "is_followed": False
    },
    {
        "id": "topic-space",
        "name": "Space Exploration",
        "slug": "space",
        "category": "space",
        "description": "Heavy launch systems, orbital telemetry, astrophysics observations, and deep space probes.",
        "follower_count": 22400,
        "is_followed": True
    },
    {
        "id": "topic-semiconductors",
        "name": "Semiconductors & Hardware",
        "slug": "semiconductors",
        "category": "technology",
        "description": "High-NA EUV lithography, GAAFET transistor packaging, optical interconnects, and foundry geopolitics.",
        "follower_count": 19700,
        "is_followed": True
    },
    {
        "id": "topic-startups",
        "name": "Venture & Startups",
        "slug": "startups",
        "category": "business",
        "description": "Seed through Series B capital formation, deep-tech spinouts, and founder playbooks.",
        "follower_count": 14100,
        "is_followed": False
    },
    {
        "id": "topic-science",
        "name": "Applied Sciences",
        "slug": "science",
        "category": "science",
        "description": "Solid-state materials, room-temperature superconductors, fusion plasma confinement, and genomics.",
        "follower_count": 26300,
        "is_followed": True
    },
    {
        "id": "topic-geopolitics",
        "name": "Geopolitics",
        "slug": "geopolitics",
        "category": "world",
        "description": "Strategic export controls, critical mineral choke-points, maritime trade routes, and regulatory treaties.",
        "follower_count": 31000,
        "is_followed": False
    },
    {
        "id": "topic-economics",
        "name": "Macroeconomics",
        "slug": "economics",
        "category": "business",
        "description": "Monetary policy, compute energy pricing, semiconductor capital expenditure, and currency liquidity.",
        "follower_count": 20800,
        "is_followed": False
    }
]

# Baseline intelligence stories curated with deep technical fidelity
NOW = datetime.utcnow()

MOCK_STORIES = [
    {
        "id": "story-001",
        "title": "Dual-Phase Reasoning Model Surpasses Human Grandmasters on Code Synthesis Benchmarks",
        "summary": "Researchers have released benchmark results for a novel dual-phase reasoning architecture that executes test-time inference tree exploration before code generation. The system achieved 91.4% on SWE-bench Verified and resolved 76% of competitive programming challenges without fine-tuning, demonstrating that latent search at inference time fundamentally shifts automated software engineering capability.",
        "why_it_matters": "For software engineering and computer science students, this marks a phase transition from simple autocomplete assistants to autonomous problem-solving engines capable of refactoring complex codebases and catching subtle race conditions.",
        "category": "ai",
        "primary_topic": "Artificial Intelligence",
        "importance_score": 94,
        "relevance_score": 98,
        "freshness_score": 96,
        "source_count": 14,
        "is_breaking": True,
        "is_saved": False,
        "relevance_reason": "High relevance to your AI and Software Engineering student profile.",
        "tags": ["AI", "Software Engineering", "Reasoning Models", "SWE-bench", "LLM Inference"],
        "created_at": NOW - timedelta(hours=1, minutes=20),
        "timeline": [
            {"time": "08:15 UTC", "title": "Paper Preprint Uploaded", "description": "ArXiv submission reveals inference compute scaling law scaling curves."},
            {"time": "09:30 UTC", "title": "SWE-bench Leaderboard Updated", "description": "Independent evaluation confirms 91.4% verified score on real-world GitHub issues."},
            {"time": "10:45 UTC", "title": "Technical Community Reaction", "description": "Core maintainers of major open-source repositories validate autonomous patch generation."}
        ],
        "entities": [
            {"name": "SWE-bench Verified", "category": "benchmark"},
            {"name": "Tree-of-Thought Search", "category": "technology"},
            {"name": "OpenAI / Anthropic Research Labs", "category": "organization"}
        ],
        "articles": [
            {
                "id": "art-101",
                "title": "Inference Compute Scaling: Why Latent Tree Search Outperforms Pure Parameter Expansion",
                "description": "Deep dive into the architectural mechanics of test-time compute versus training-time parameter scaling.",
                "url": "https://example.com/research/inference-scaling",
                "author": "Dr. Elena Vance",
                "published_at": NOW - timedelta(hours=1, minutes=15),
                "source_name": "MIT Technology Review",
                "source_domain": "technologyreview.com"
            },
            {
                "id": "art-102",
                "title": "Software Engineering Benchmarks Reset as Dual-Phase Agent Smashes Historical Records",
                "description": "Analysis of real-world bug fixes submitted autonomously to active repositories.",
                "url": "https://example.com/engineering/dual-phase-agent",
                "author": "Marcus Thorne",
                "published_at": NOW - timedelta(hours=1, minutes=45),
                "source_name": "ACM Queue",
                "source_domain": "queue.acm.org"
            },
            {
                "id": "art-103",
                "title": "Industry Reaction: The Economic Implications of High-Verification Automated Code Systems",
                "description": "Perspectives from principal engineers and venture investors on software productivity.",
                "url": "https://example.com/analysis/ai-code-economics",
                "author": "Sarah Lin",
                "published_at": NOW - timedelta(hours=2),
                "source_name": "The Information",
                "source_domain": "theinformation.com"
            }
        ]
    },
    {
        "id": "story-002",
        "title": "Critical Zero-Day in Linux eBPF Subsystem Weaponized for Cloud Container Escapes",
        "summary": "The Linux Kernel Security Team and CERT have issued emergency advisory CVE-2026-2819 regarding a flaw in the Extended Berkeley Packet Filter (eBPF) verifier logic. Exploitation permits an unprivileged local user inside a standard container to bypass namespace barriers and execute arbitrary root-level ring-0 kernel code on host hypervisors.",
        "why_it_matters": "Immediate mitigation required for any developer running multi-tenant Kubernetes clusters or bare-metal development servers. It illustrates the security trade-offs between kernel observability and attack surface enlargement.",
        "category": "cybersecurity",
        "primary_topic": "Cybersecurity",
        "importance_score": 96,
        "relevance_score": 92,
        "freshness_score": 98,
        "source_count": 19,
        "is_breaking": True,
        "is_saved": False,
        "relevance_reason": "Direct impact on your Cloud Infrastructure and Operating Systems security coursework.",
        "tags": ["Cybersecurity", "Linux Kernel", "eBPF", "Vulnerability", "Kubernetes", "CVE-2026-2819"],
        "created_at": NOW - timedelta(hours=2, minutes=45),
        "timeline": [
            {"time": "06:00 UTC", "title": "CVE-2026-2819 Published", "description": "Advisory assigned CVSS score 9.8 (Critical)."},
            {"time": "07:20 UTC", "title": "Kernel Patch Backported", "description": "Stable trees 6.6 LTS, 6.12 LTS, and 6.14 release immediate point revisions."},
            {"time": "08:50 UTC", "title": "Major Cloud Providers Roll Hot-Patches", "description": "AWS, GCP, and Azure deploy live-patch hypervisor mitigations without node reboot."}
        ],
        "entities": [
            {"name": "CVE-2026-2819", "category": "vulnerability"},
            {"name": "Linux Kernel Verifier", "category": "technology"},
            {"name": "Kubernetes / OCI Containers", "category": "technology"},
            {"name": "CISA / CERT", "category": "organization"}
        ],
        "articles": [
            {
                "id": "art-201",
                "title": "Urgent Advisory: Kernel Verifier Logic Hole Exposes Container Hosts to Arbitrary Code Execution",
                "description": "Technical breakdown of the register state truncation bug in eBPF verification path.",
                "url": "https://example.com/security/ebpf-cve-2026-2819",
                "author": "Kees Cook",
                "published_at": NOW - timedelta(hours=2, minutes=30),
                "source_name": "LWN.net",
                "source_domain": "lwn.net"
            },
            {
                "id": "art-202",
                "title": "Cloud Infrastructure Scrambles to Patch Critical Container Breakout Flaw",
                "description": "Enterprise cloud response and zero-downtime live patching verification.",
                "url": "https://example.com/security/container-breakout",
                "author": "Dan Goodin",
                "published_at": NOW - timedelta(hours=3),
                "source_name": "Ars Technica",
                "source_domain": "arstechnica.com"
            }
        ]
    },
    {
        "id": "story-003",
        "title": "TSMC Reports 78% Defect-Free Yield on 2nm GAAFET Nodes Ahead of 2026 Production Window",
        "summary": "Taiwan Semiconductor Manufacturing Company (TSMC) confirmed during its quarterly technology symposium that trial production runs for its N2 (2-nanometer class) process utilizing Gate-All-Around nanosheet transistors have reached an industry-leading 78% defect-free yield. High-volume manufacturing is now confirmed to begin in H1 2026.",
        "why_it_matters": "N2 represents the industry's shift away from FinFET architectures to nanosheets, providing a 15% speed increase at identical power or a 30% power reduction. Essential for mobile processors and next-gen AI inference clusters.",
        "category": "technology",
        "primary_topic": "Semiconductors & Hardware",
        "importance_score": 88,
        "relevance_score": 90,
        "freshness_score": 90,
        "source_count": 11,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "High relevance to your Hardware Architecture and Semiconductor interests.",
        "tags": ["Semiconductors", "TSMC", "GAAFET", "Hardware", "Nanosheets", "2nm"],
        "created_at": NOW - timedelta(hours=4, minutes=10),
        "timeline": [
            {"time": "03:00 UTC", "title": "TSMC Symposium Keynote", "description": "CTO discloses N2 trial wafer metrics from Fab 20 in Hsinchu."},
            {"time": "04:30 UTC", "title": "Equipment Supply Update", "description": "ASML confirms delivery of High-NA EUV lithography systems to Hsinchu test lines."}
        ],
        "entities": [
            {"name": "TSMC", "category": "organization"},
            {"name": "ASML", "category": "organization"},
            {"name": "GAAFET Nanosheet", "category": "technology"}
        ],
        "articles": [
            {
                "id": "art-301",
                "title": "TSMC 2nm GAAFET Wafer Yield Exceeds Internal Milestones at Fab 20",
                "description": "In-depth silicon analysis of nanosheet capacitance and leakage improvements.",
                "url": "https://example.com/hardware/tsmc-2nm-yield",
                "author": "Anton Shilov",
                "published_at": NOW - timedelta(hours=4),
                "source_name": "AnandTech",
                "source_domain": "anandtech.com"
            }
        ]
    },
    {
        "id": "story-004",
        "title": "ESA Juice Spacecraft Executes Unprecedented Double Gravity Assist Around Moon and Earth",
        "summary": "The European Space Agency's Jupiter Icy Moons Explorer (Juice) has completed a world-first Lunar-Earth gravity assist maneuver, skimming just 750 kilometers above the lunar crater surface before swinging past Earth 36 hours later. The maneuver shaved 3.2 km/s of velocity requirement and saved 150 kg of onboard propellant for its 2031 orbital insertion around Ganymede.",
        "why_it_matters": "Demonstrates precision orbital mechanics and deep-space trajectory optimization under non-linear gravitational perturbations, preserving valuable scientific mission lifetime.",
        "category": "space",
        "primary_topic": "Space Exploration",
        "importance_score": 82,
        "relevance_score": 86,
        "freshness_score": 85,
        "source_count": 8,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "Matches your Space Exploration and Physics tracking filters.",
        "tags": ["Space", "ESA", "Juice Probe", "Orbital Mechanics", "Astrophysics"],
        "created_at": NOW - timedelta(hours=6),
        "timeline": [
            {"time": "Yesterday", "title": "Lunar Closest Approach", "description": "Juice passed within 750 km of the lunar south pole."},
            {"time": "02:15 UTC", "title": "Perigee Earth Flyby", "description": "Atmospheric telemetry verified exact delta-v insertion vector."}
        ],
        "entities": [
            {"name": "Juice Spacecraft", "category": "technology"},
            {"name": "European Space Agency", "category": "organization"},
            {"name": "Ganymede", "category": "concept"}
        ],
        "articles": [
            {
                "id": "art-401",
                "title": "Braking via Moon and Earth: How Juice Pulled Off an Orbital Mechanics Miracle",
                "description": "Flight dynamics telemetry review from ESOC Darmstadt control center.",
                "url": "https://example.com/space/juice-double-flyby",
                "author": "Jonathan Amos",
                "published_at": NOW - timedelta(hours=5, minutes=45),
                "source_name": "BBC Science",
                "source_domain": "bbc.co.uk"
            }
        ]
    },
    {
        "id": "story-005",
        "title": "Department of Justice Proposes Unbundling Framework for Cloud Hyperscaler Compute Stacks",
        "summary": "The US Department of Justice Antitrust Division has filed an amicus brief proposing structural separation between proprietary cloud virtualization infrastructure, GPU allocation queues, and high-level developer software suites. The filing argues that exclusive compute agreements stifle independent AI startup competition.",
        "why_it_matters": "If adopted into federal regulatory frameworks, developers and independent startups could access enterprise-grade GPU clusters without mandatory lock-in to proprietary cloud runtime ecosystems.",
        "category": "business",
        "primary_topic": "Macroeconomics",
        "importance_score": 84,
        "relevance_score": 78,
        "freshness_score": 80,
        "source_count": 16,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "Impacts cloud hosting costs, AI startup viability, and software economics.",
        "tags": ["Business", "Antitrust", "Cloud Compute", "GPU Allocation", "DOJ"],
        "created_at": NOW - timedelta(hours=7, minutes=30),
        "timeline": [
            {"time": "14:00 UTC", "title": "Legal Brief Lodged", "description": "Federal court in Washington receives 84-page competitive assessment."},
            {"time": "16:20 UTC", "title": "Hyperscaler Consortium Responds", "description": "Industry trade association issues statement asserting integrated efficiencies."}
        ],
        "entities": [
            {"name": "US Department of Justice", "category": "organization"},
            {"name": "Cloud Computing Infrastructure", "category": "technology"}
        ],
        "articles": [
            {
                "id": "art-501",
                "title": "DOJ Takes Aim at GPU Tier Bundling in Landmark Tech Competition Filing",
                "description": "Analysis of legal precedents and potential remedies for artificial compute scarcity.",
                "url": "https://example.com/policy/cloud-antitrust-filing",
                "author": "David McCabe",
                "published_at": NOW - timedelta(hours=7),
                "source_name": "The Wall Street Journal",
                "source_domain": "wsj.com"
            }
        ]
    },
    {
        "id": "story-006",
        "title": "Solid-State Lithium-Metal Anode Cells Pass 1,200 Fast-Charge Cycles with 92% Capacity Retention",
        "summary": "Materials science researchers in collaboration with QuantumScape and national laboratories have verified third-party endurance test results for an anodeless lithium-metal solid-state battery. The cells completed 1,200 continuous 15-minute 4C fast-charge cycles at room temperature while preserving 92% initial volumetric energy density.",
        "why_it_matters": "Overcomes the decades-long dendrite short-circuit failure mode in lithium-metal anodes. Paves the way for electric vehicles with 500-mile real-world ranges and sub-15-minute charging without thermal runaway risk.",
        "category": "science",
        "primary_topic": "Applied Sciences",
        "importance_score": 86,
        "relevance_score": 84,
        "freshness_score": 88,
        "source_count": 10,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "High interest in energy storage materials science and clean tech engineering.",
        "tags": ["Science", "Batteries", "Solid-State", "Materials Engineering", "Energy"],
        "created_at": NOW - timedelta(hours=8, minutes=15),
        "timeline": [
            {"time": "Yesterday", "title": "Peer-Reviewed Study in Nature Materials", "description": "Synchrotron X-ray imaging confirms absence of dendritic voids during fast charging."},
            {"time": "06:00 UTC", "title": "Pilot Manufacturing Scaleup", "description": "Contract manufacturer announces automated roll-to-roll separator coating facility."}
        ],
        "entities": [
            {"name": "QuantumScape / National Labs", "category": "organization"},
            {"name": "Ceramic Solid-State Separator", "category": "technology"},
            {"name": "Nature Materials", "category": "organization"}
        ],
        "articles": [
            {
                "id": "art-601",
                "title": "Lithium-Metal Solid State Reaches Automotive Durability Benchmark",
                "description": "Experimental verification of ceramic-polymer hybrid separator performance.",
                "url": "https://example.com/energy/solid-state-breakthrough",
                "author": "Dr. Aris Thorne",
                "published_at": NOW - timedelta(hours=8),
                "source_name": "Nature Energy",
                "source_domain": "nature.com"
            }
        ]
    },
    {
        "id": "story-007",
        "title": "NIST and CISA Mandate Post-Quantum Cryptography Migration Roadmaps for Critical Banking",
        "summary": "The National Institute of Standards and Technology (NIST) alongside CISA has issued an enforceable directive establishing 2028 as the formal cutoff for legacy RSA-2048 and ECC public key infrastructure across federally regulated banking institutions. Systems must transition to ML-KEM (Kyber) and ML-DSA (Dilithium) post-quantum algorithms.",
        "why_it_matters": "Addresses the 'Harvest Now, Decrypt Later' threat vector. Software engineers will see massive rewrites across TLS stacks, authentication tokens, hardware security modules (HSMs), and cryptographic libraries.",
        "category": "cybersecurity",
        "primary_topic": "Cybersecurity",
        "importance_score": 89,
        "relevance_score": 93,
        "freshness_score": 86,
        "source_count": 15,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "Directly impacts security protocols, cryptographic implementations, and backend engineering.",
        "tags": ["Cybersecurity", "Post-Quantum", "Cryptography", "NIST", "ML-KEM", "Kyber"],
        "created_at": NOW - timedelta(hours=10),
        "timeline": [
            {"time": "Two Days Ago", "title": "Final Standards Published", "description": "FIPS 203, 204, and 205 formalized for global implementation."},
            {"time": "09:00 UTC", "title": "Regulatory Mandate Issued", "description": "Federal Financial Institutions Examination Council publishes compliance timetable."}
        ],
        "entities": [
            {"name": "NIST", "category": "organization"},
            {"name": "CISA", "category": "organization"},
            {"name": "ML-KEM (CRYSTALS-Kyber)", "category": "technology"}
        ],
        "articles": [
            {
                "id": "art-701",
                "title": "Banking Core Systems Face Mandatory Post-Quantum Upgrade Timeline",
                "description": "How financial legacy systems plan to replace RSA key exchanges with lattice-based cryptography.",
                "url": "https://example.com/infosec/pqc-banking-mandate",
                "author": "Lily Hay Newman",
                "published_at": NOW - timedelta(hours=9, minutes=30),
                "source_name": "Wired Security",
                "source_domain": "wired.com"
            }
        ]
    },
    {
        "id": "story-008",
        "title": "European Union AI Act Board Releases Standardized Watermarking and Audit Protocol",
        "summary": "The European AI Office has finalized its Technical Implementation Guidance on synthetic content provenance under Articles 50 and 52 of the EU AI Act. Commercial model providers must embed cryptographically verifiable C2PA metadata and latent watermarking resistant to re-encoding across all generated text, audio, and visual outputs.",
        "why_it_matters": "Enforces global architectural requirements on generative AI APIs and model serving frameworks operating in European jurisdictions, impacting model inference latency and client verification tooling.",
        "category": "world",
        "primary_topic": "Geopolitics",
        "importance_score": 87,
        "relevance_score": 81,
        "freshness_score": 82,
        "source_count": 17,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "High relevance to regulatory frameworks governing software and AI deployments.",
        "tags": ["World", "EU AI Act", "Provenance", "C2PA", "AI Regulation", "Compliance"],
        "created_at": NOW - timedelta(hours=12),
        "timeline": [
            {"time": "07:30 UTC", "title": "Draft Annex Finalized", "description": "Article 50 implementation details ratified by member state delegates."},
            {"time": "11:00 UTC", "title": "API Specification Open-Sourced", "description": "Reference C2PA manifest verification library published under Apache 2.0."}
        ],
        "entities": [
            {"name": "European AI Office", "category": "organization"},
            {"name": "C2PA Coalition", "category": "organization"},
            {"name": "EU AI Act", "category": "concept"}
        ],
        "articles": [
            {
                "id": "art-801",
                "title": "EU Standardizes Watermarking Requirements for Generative AI Pipelines",
                "description": "Technical analysis of how C2PA content credentials will be verified at web scale.",
                "url": "https://example.com/tech-policy/eu-ai-watermarking",
                "author": "Javier Espinoza",
                "published_at": NOW - timedelta(hours=11, minutes=30),
                "source_name": "Financial Times",
                "source_domain": "ft.com"
            }
        ]
    },
    {
        "id": "story-009",
        "title": "Neutral-Atom Quantum Processor Demonstrates Fault-Tolerant Logical Qubit Gate Array",
        "summary": "Harvard, QuEra Computing, and MIT researchers have demonstrated two-qubit entangling gates across 48 fault-tolerant logical qubits using optical tweezers in a 3D neutral-atom architecture. By utilizing 3D toric surface codes, the error rate per logical operation dropped below physical qubit noise thresholds for the first time.",
        "why_it_matters": "A critical experimental verification that quantum error correction works in practice, bringing commercially viable fault-tolerant quantum algorithms significantly closer than previously forecasted.",
        "category": "science",
        "primary_topic": "Applied Sciences",
        "importance_score": 91,
        "relevance_score": 88,
        "freshness_score": 80,
        "source_count": 12,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "Matches your Quantum Computing and Physics exploration preferences.",
        "tags": ["Science", "Quantum Computing", "Logical Qubits", "Neutral Atoms", "Error Correction"],
        "created_at": NOW - timedelta(hours=14),
        "timeline": [
            {"time": "Yesterday", "title": "Nature Physics Cover Article", "description": "Experimental verification of 48 transversal logical CZ gates."},
            {"time": "12:00 UTC", "title": "Architecture Roadmap Update", "description": "Consortium outlines commercial 10,000-physical-atom system for 2027."}
        ],
        "entities": [
            {"name": "QuEra Computing", "category": "organization"},
            {"name": "Harvard Quantum Initiative", "category": "organization"},
            {"name": "Neutral-Atom Array", "category": "technology"}
        ],
        "articles": [
            {
                "id": "art-901",
                "title": "Error-Corrected Quantum Computing Crosses the Break-Even Threshold",
                "description": "In-depth physics breakdown of Rydberg atom array interaction and gate fidelity.",
                "url": "https://example.com/quantum/fault-tolerant-neutral-atoms",
                "author": "Dr. Sophia Hayes",
                "published_at": NOW - timedelta(hours=13, minutes=30),
                "source_name": "Quanta Magazine",
                "source_domain": "quantamagazine.org"
            }
        ]
    },
    {
        "id": "story-010",
        "title": "DARPA AIxCC Finals Reveal Autonomous Agents Capable of Discovering and Patching Zero-Days in 15 Minutes",
        "summary": "The Artificial Intelligence Cyber Challenge (AIxCC) finals concluded with top autonomous cyber-reasoning systems (CRSs) demonstrating zero-human-in-the-loop vulnerability remediation. The leading agent autonomously discovered a memory corruption bug in an open-source web server, synthesized a proof-of-concept exploit, wrote a patch that passed 100% of regression tests, and deployed it within 14 minutes.",
        "why_it_matters": "Direct preview of the future of automated defense vs. offensive operations in software systems. It radically changes the economics of zero-day discovery and patch management.",
        "category": "cybersecurity",
        "primary_topic": "Cybersecurity",
        "importance_score": 93,
        "relevance_score": 95,
        "freshness_score": 79,
        "source_count": 13,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "High relevance to your Cybersecurity and Automated Software Engineering interests.",
        "tags": ["Cybersecurity", "AIxCC", "Autonomous Defense", "Zero-Day", "DARPA"],
        "created_at": NOW - timedelta(hours=16),
        "timeline": [
            {"time": "Yesterday", "title": "Finals Competition Round", "description": "Synthetic multi-tier challenges evaluated under strict sandboxes."},
            {"time": "15:00 UTC", "title": "DARPA Awards Announced", "description": "Top prize awarded to hybrid symbolic-execution and LLM reasoning agent."}
        ],
        "entities": [
            {"name": "DARPA", "category": "organization"},
            {"name": "AIxCC Challenge", "category": "benchmark"},
            {"name": "Cyber Reasoning Systems (CRS)", "category": "technology"}
        ],
        "articles": [
            {
                "id": "art-1001",
                "title": "Autonomous Software Defense Comes of Age at DARPA AIxCC Finals",
                "description": "How autonomous agents combine static analysis with neural reasoning to patch bugs safely.",
                "url": "https://example.com/security/darpa-aixcc-finals",
                "author": "Kim Zetter",
                "published_at": NOW - timedelta(hours=15, minutes=45),
                "source_name": "Dark Reading",
                "source_domain": "darkreading.com"
            }
        ]
    },
    {
        "id": "story-011",
        "title": "Global Semiconductor Capital Expenditure Hits Record High Amid Resilient Macroeconomic Demand",
        "summary": "International trade monitors and central bank economic bulletins report that global semiconductor equipment outlays and compute infrastructure investments reached a new all-time high of $128 billion this fiscal year. The capital expenditure wave reflects macroeconomic reallocation from legacy hardware toward domestic wafer fabrication and next-generation packaging plants.",
        "why_it_matters": "Demonstrates structural economic shifts as sovereign wealth funds and institutional capital treat microchip fabrication as vital critical infrastructure akin to national energy grids.",
        "category": "economy",
        "primary_topic": "Macroeconomics",
        "importance_score": 83,
        "relevance_score": 80,
        "freshness_score": 85,
        "source_count": 8,
        "is_breaking": False,
        "is_saved": False,
        "relevance_reason": "Direct insight into macroeconomic capital expenditure cycles and technology market trends.",
        "tags": ["Economy", "Semiconductors", "CapEx", "Global Trade", "Macroeconomics"],
        "created_at": NOW - timedelta(hours=10),
        "timeline": [
            {"time": "08:00 UTC", "title": "Economic Report Published", "description": "Global Trade Monitor releases annual tech hardware capital analysis."},
            {"time": "11:30 UTC", "title": "Central Bank Commentary", "description": "Monetary bulletin highlights industrial CapEx resilience."}
        ],
        "entities": [
            {"name": "Federal Reserve", "category": "organization"},
            {"name": "Bank for International Settlements", "category": "organization"},
            {"name": "Global Semiconductor Alliance", "category": "organization"}
        ],
        "articles": [
            {
                "id": "art-1101",
                "title": "Record Semiconductor Outlays Signal Sustained Macroeconomic Investment Shift",
                "description": "How global capital expenditure is restructuring international tech manufacturing and logistics.",
                "url": "https://example.com/economy/semiconductor-capex-record",
                "author": "Stephanie Baker",
                "published_at": NOW - timedelta(hours=9, minutes=30),
                "source_name": "Financial Markets Wire",
                "source_domain": "fmwire.com"
            }
        ]
    }
]

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "user_id": "student_user",
    "interests": [
        "AI",
        "Software Engineering",
        "Cybersecurity",
        "Semiconductors",
        "Space",
        "Science"
    ],
    "breaking_sensitivity": "standard",
    "importance_threshold": 50,
    "preferred_sources": [
        "MIT Technology Review",
        "LWN.net",
        "Ars Technica",
        "AnandTech",
        "Quanta Magazine",
        "ACM Queue"
    ],
    "hidden_topics": [],
    "theme": "terminal-dark",
    "updated_at": NOW
}

USER_INTERACTIONS: List[Dict[str, Any]] = []

class NewsService:
    """
    Operational intelligence service providing filtered and personalized news stories.
    """
    def __init__(self):
        self._stories = list(MOCK_STORIES)
        self._topics = list(MOCK_TOPICS)
        self._preferences = dict(DEFAULT_PREFERENCES)
        self._saved_ids = set()

    def get_all_stories(
        self,
        category: Optional[str] = None,
        topic: Optional[str] = None,
        section: Optional[str] = None,
        search: Optional[str] = None,
        min_importance: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for s in self._stories:
            # Annotate saved status
            story_copy = dict(s)
            story_copy["is_saved"] = story_copy["id"] in self._saved_ids

            # Filter by category
            if category and story_copy["category"].lower() != category.lower():
                continue

            # Filter by topic
            if topic and (topic.lower() not in [t.lower() for t in story_copy["tags"]] and topic.lower() != story_copy["primary_topic"].lower()):
                continue

            # Filter by section
            if section == "breaking" and not story_copy.get("is_breaking", False):
                continue
            elif section == "important" and story_copy.get("importance_score", 0) < 85:
                continue

            # Filter by importance threshold
            if min_importance is not None and story_copy.get("importance_score", 0) < min_importance:
                continue

            # Search keyword match
            if search:
                query = search.lower()
                title_match = query in story_copy["title"].lower()
                summary_match = query in story_copy["summary"].lower()
                tags_match = any(query in tag.lower() for tag in story_copy.get("tags", []))
                entity_match = any(query in e["name"].lower() for e in story_copy.get("entities", []))
                if not (title_match or summary_match or tags_match or entity_match):
                    continue

            results.append(story_copy)

        # Sort by importance and freshness
        results.sort(key=lambda x: (x.get("importance_score", 0) * 0.6 + x.get("freshness_score", 0) * 0.4), reverse=True)
        return results

    get_stories = get_all_stories

    def get_story_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        for s in self._stories:
            if s["id"] == story_id:
                story_copy = dict(s)
                story_copy["is_saved"] = story_id in self._saved_ids
                return story_copy
        return None

    def get_topics(self) -> List[Dict[str, Any]]:
        return self._topics

    def update_topic_follow(self, topic_id: str, is_followed: bool) -> Optional[Dict[str, Any]]:
        for t in self._topics:
            if t["id"] == topic_id or t["slug"] == topic_id:
                t["is_followed"] = is_followed
                t["follower_count"] += 1 if is_followed else -1
                return t
        return None

    def get_preferences(self) -> Dict[str, Any]:
        return self._preferences

    def update_preferences(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in updates.items():
            if v is not None:
                self._preferences[k] = v
        self._preferences["updated_at"] = datetime.utcnow()
        return self._preferences

    def record_interaction(self, story_id: str, interaction_type: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        interaction = {
            "id": f"int-{len(USER_INTERACTIONS) + 1}",
            "story_id": story_id,
            "interaction_type": interaction_type,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow()
        }
        USER_INTERACTIONS.append(interaction)

        if interaction_type == "save":
            self._saved_ids.add(story_id)
        elif interaction_type == "unsave":
            self._saved_ids.discard(story_id)

        return interaction

    def get_saved_stories(self) -> List[Dict[str, Any]]:
        return [
            dict(s, is_saved=True)
            for s in self._stories
            if s["id"] in self._saved_ids
        ]

news_service = NewsService()
