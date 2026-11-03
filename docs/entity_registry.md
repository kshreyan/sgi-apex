# Entity registry: Phase 0 discovery audit

Checked 2026-11-03 against public sources. The machine-readable registry is `configs/entities/entity_registry.csv`, written to `data/master/entity_registry.parquet` by `sgi registry`.

**Rule:** group-level reporting stays blocked while any programme rolls up to an entity whose confidence is `none` or `low` (`registry.reconcile`).

## A. Verified organisation map

```text
Subhwanti Sudama Rai Foundation (SSRF)               legal form UNVERIFIED · confidence LOW
└── Subhwanti Group of Institutions (SGI), est. 2011 brand · HIGH (subhwanti.com)
    ├── SIWAN CAMPUS (Pachaura, PO Aghaila, Siwan)
    │   └── Subhwanti Institute of Education (SIE)
    │       ├── School of Education         NCTE · JPU Chapra · BSEB          B.Ed, D.El.Ed
    │       ├── School of Nursing           BNRC · BUHS · State NOC           B.Sc Nursing, GNM (+ANM, P.B.B.Sc per third party)
    │       └── School of Info. Sci. & Mgmt AICTE · AKU                       BBA, BCA, MBA, MCA (campus split unverified)
    └── BETTIAH CAMPUS (Vill Senuaria, NH-28B, Majhaulia, W. Champaran 845454)
        ├── Subhwanti Institute of Professional Education (SIPE), est. 2020 per third party
        │   ├── School of Pharmacy          PCI · BUHS (AKU per third party: CONFLICT)   D.Pharm, B.Pharm, M.Pharm
        │   ├── School of Law               BCI · BRABU Muzaffarpur          LLB (list unverified)
        │   └── School of Info. Sci. & Mgmt AICTE · AKU
        ├── Hi-Tech Polytechnic College      AICTE · SBTE Patna (affiliated 2016 per third party)   Diplomas
        └── Hi-Tech Engineering College      AICTE · BEU Patna                 B.Tech (branches unverified)

HEALTHCARE: Chakia hospital                         NOT VERIFIED · confidence NONE
```

Leadership listed publicly at subhwanti.com/leadership.php: Chairman, President, Director General and Group Director.

## B. Public footprint audit

| Asset | Finding |
|---|---|
| subhwanti.com | Group site. Lists institutes and schools, accreditation page with certificates, application form (Teacher's Training, Nursing, Management, Diploma, B.Tech, Pharmacy, Law). Several links point to `#`; the "Hi-Tech Affiliation 23-24" link points to the NCTE PDF (broken evidence link). |
| pharma.subhwanti.com | School of Pharmacy microsite. B.Pharm, M.Pharm, D.Pharm. PCI and BUHS. Supports Bihar Student Credit Card (BSCC). Footer misspells the name ("Subhwant"). M.Pharm card links to the D.Pharm page. |
| Social | Facebook (subhwantigroupsiwan), Instagram (subhwantigroup / subhwantigroupsiwan: two handles), YouTube (two handles), LinkedIn. |
| Third-party | Careers360: B.Ed 100 seats; D.Pharm 60 / B.Pharm 100. Collegedunia: Hi-Tech Polytechnic is a unit of the Subhwanti group under the Subhwanti-Sudama-Rai Foundation. Some directory claims (e.g. "UGC approved") conflict with official pages and are **not** accepted. |

Every regulator listed on the accreditation page without a matching certificate (BSEB, BUHS for Pharmacy, SBTE, BEU, BCI) is a **document-evidence gap**, tracked for the compliance graph.

## C. Hospital identity verification

**Result: NOT VERIFIED.** No public source links SSRF or SGI to a hospital in Chakia, based on searches on 2026-11-03 (English-language web, East Champaran district portal, PM-JAY listings, Justdial). Chakia also exists in Chandauli, Uttar Pradesh, so the district itself must be confirmed. Facilities found in Chakia (East Champaran) include government facilities (PHC/Referral Hospital/SDH) and several private hospitals. **None is attributed to the Foundation, and the registry does not guess.**

Needed to close this item: clinical-establishment registration certificate, the legal operator (Foundation or a separate entity), any PM-JAY / NABH / pharmacy licences, and its official name.

## Historical names to reconcile

| Name | Status |
|---|---|
| Subhwanti Institute of Health Education | Not on current website. Possibly a former name of the Nursing school. UNVERIFIED |
| Subhwanti Institute of Management & Technology | Not on current website. Possibly a predecessor of SISM or Hi-Tech. UNVERIFIED |
| Subhwanti Institute of Professional Education | **Current**: Bettiah institute (Pharmacy, Law, SISM) |

## Open questions for the Foundation office

1. Legal form and registration number of SSRF (trust, society or Section 8 company), plus 12A/80G status.
2. Is each college a separate legal entity, or a unit of the Foundation?
3. Pharmacy affiliating university: BUHS (website) or AKU (third party)?
4. Sanctioned intake per programme, from current approval letters. Most intakes in `programmes.csv` are **placeholders**.
5. Engineering and diploma branches.
6. The hospital (section C).
