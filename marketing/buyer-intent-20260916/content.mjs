// Reviewed corrections preserve the existing routes and subject coverage.
export const corrections = [
  {
    family: 'comparisons', slug: 'catalog-sale-vs-catalog-loan', route: '/compare/catalog-sale-vs-catalog-loan/',
    patch: {
      title: 'Catalog Sale vs. Catalog Loan: Rights, Costs and Trade-Offs',
      metaDescription: 'Compare a music catalog sale, a catalog-backed loan and a royalty advance. Understand rights, retained income, repayment and the questions to ask before signing.',
      introduction: 'A catalog sale exchanges defined rights or royalty interests for a purchase price. A catalog-backed loan creates a repayment obligation secured under the agreement. A royalty advance can use a different structure again: do not assume every upfront payment is a loan. For independent artists and labels in any genre, compare the rights committed, net cash available, future income retained and consequences if royalties fall. SPACE considers direct catalog purchases; it does not offer a loan or royalty-advance product.',
      optionA: {
        description: 'A catalog sale transfers the interests specified in the agreement. It can cover selected recordings, a defined share or all of the seller\'s interest in the included catalog. The buyer receives the income attached to the interest purchased, not automatically every royalty the artist or label earns.',
        pros: [
          'An agreed purchase price for the interests included, rather than an assumed market multiple',
          'Future income performance on the sold interest passes economically to the buyer, subject to the contract',
          'An outright sale is not a loan repayment schedule; continuing contractual duties still need review',
          'The parties can define which administration and reporting duties transfer',
          'Tax consequences can be evaluated before committing, with jurisdiction-specific advice',
          'No loan interest on an outright purchase, although transaction costs and deductions may apply',
          'Existing recordings can be separated from future creative work in the agreed scope'
        ],
        cons: [
          'You give up the rights and future income included in the sale for its agreed duration',
          'Growth in the sold interest benefits the buyer; genre alone does not establish a growth forecast',
          'The personal significance of parting with your work is a separate consideration from price',
          'Licensing and approval rights depend on the agreement and any rights you reserve',
          'An upfront payment may replace income you need for future operating costs',
          'Legal, valuation and other transaction costs reduce the cash available to you',
          'Taxes, payment timing and withholding require advice specific to the seller and transaction'
        ],
        bestFor: 'Owners willing to explore transferring a clearly defined interest and compare a written offer with the income and rights they would retain. This is not a recommendation to sell, and choosing not to transact remains an option.'
      },
      optionB: {
        description: 'A catalog-backed loan involves borrowing under a lender\'s agreement, potentially secured against rights or royalty income. Ownership, collection arrangements, guarantees, repayment obligations and default remedies must be checked in the actual documents. Retaining legal title does not mean retaining unrestricted use of all royalties.',
        pros: [
          'Ownership may remain with you, subject to security and default provisions',
          'Capital can be available without an outright sale, if a lender approves the application',
          'A loan and a sale have different tax questions; obtain advice rather than assuming either is tax-free',
          'Compare the total repayment cost, including interest and fees, before selecting an offer',
          'You may retain exposure to future growth as well as the risk of lower income',
          'Early repayment or refinancing may be possible if the agreement permits it',
          'Release of security and collection instructions should be documented when obligations are satisfied'
        ],
        cons: [
          'Available capital is lender- and catalog-specific; no universal revenue multiple is established here',
          'Interest, fees and other charges can increase the total repayment cost',
          'Payment schedules and obligations can continue even when royalty receipts fall',
          'Default can put pledged rights or other collateral at risk, depending on the agreement',
          'Some royalty income may be redirected to meet repayment obligations',
          'Reporting and financial-management duties can continue through the arrangement',
          'Covenants or security arrangements may limit licensing, transfers or administration changes'
        ],
        bestFor: 'Owners comparing the cost and obligations of borrowing with a sale or retaining their catalog. Affordability under lower-income scenarios and the consequences of default need independent assessment; a growing genre is not evidence that borrowing is suitable.'
      },
      features: [
        {feature:'Capital Access',optionA:'Individually negotiated purchase price',optionB:'Individual lender assessment and terms'},
        {feature:'Ownership',optionA:'Only the interests defined in the sale transfer',optionB:'Depends on security and default provisions'},
        {feature:'Ongoing Revenue',optionA:'Income from excluded or retained interests can remain',optionB:'Collection and available cash depend on repayment terms'},
        {feature:'Risk',optionA:'Lost income and continuing warranties or other duties',optionB:'Repayment, covenant and collateral risks'},
        {feature:'Tax Treatment',optionA:'Seller-, asset- and jurisdiction-specific advice required',optionB:'Seller-, instrument- and jurisdiction-specific advice required'},
        {feature:'Future Upside',optionA:'Buyer benefits on the sold interest; retained interests remain exposed',optionB:'May remain with the owner subject to agreement performance'},
        {feature:'Total Cost',optionA:'Future income given up plus transaction costs and deductions',optionB:'Principal, interest, fees and other agreed charges'},
        {feature:'Time Commitment',optionA:'Closing plus any continuing duties in the agreement',optionB:'Agreed term and any extension or default provisions'}
      ],
      verdict: 'There is no universal winner. Put the same catalog scope and income assumptions beside each written proposal, then compare net proceeds, retained cash flow, control, total obligations and downside scenarios. A label must account for money owed to artists and producers before treating royalty receipts as spendable income. Keeping the catalog and reducing or delaying the project is also a valid option. SPACE is a potential buyer, not an independent adviser or lender; seek independent legal, financial and tax advice.',
      faq: [
        {question:'Can I get a catalog loan on a small catalog?',answer:'Eligibility depends on the provider, documented income, the rights available and the proposed structure. This page does not establish a minimum revenue level or a lender approval. A royalty advance may not be a loan. SPACE does not offer catalog loans; its free application is for a potential catalog purchase.'},
        {question:'What interest rates do catalog loans typically carry?',answer:'No verified market-wide rate range is established here. Ask a lender for the total repayment amount, fees, payment schedule, security, guarantees and default terms. For an advance, examine the recoupment amount and end conditions rather than assuming that a product with no stated interest has no economic cost.'}
      ]
    }
  },
  {
    family: 'comparisons', slug: 'partial-sale-vs-full-sale', route: '/compare/partial-sale-vs-full-sale/',
    patch: {
      introduction: 'A partial catalog sale can mean selected recordings or a defined share of the rights or royalties you control. A full sale means all of your interest in the agreed catalog, not necessarily every right in every song, and not automatically your future releases. For independent artists and labels across genres, the useful comparison is net cash now versus income, rights and responsibilities retained. Neither route is always better, and keeping a majority percentage does not by itself guarantee licensing or creative control.',
      optionA: {
        description:'A partial transaction may cover a subset of recordings, a percentage of an owned interest, or a defined royalty-income interest. Co-ownership is not the structure of every deal. Specify tracks, rights, shares, income streams, territory and duration before comparing prices.',
        pros:[
          'Raise capital while retaining the income attributable to interests outside the sale',
          'Keep exposure to future growth on the retained interest, with no guarantee of growth',
          'Negotiate reserved approvals and administration rights instead of relying on ownership percentage alone',
          'Retain a connection to part of the catalog if that matters to your plans',
          'A later sale may be possible, subject to the original agreement and required consents',
          'Evaluate any promised buyer services separately and require them to be documented',
          'Propose the selected recordings or share that matches the scope you want reviewed'
        ],
        cons:[
          'The price need not be a simple percentage of a hypothetical whole-catalog valuation',
          'Ongoing collection, reporting or co-ownership arrangements need clear responsibilities',
          'Revenue splits, deductions and payment instructions need accurate administration',
          'Control, transfer restrictions and scope can affect the price of the interest',
          'Approval or licensing disputes are possible if responsibilities are unclear',
          'The first agreement may restrict a later sale of the remaining interest',
          'Professional costs must be considered relative to the actual net proceeds'
        ],
        bestFor:'Owners who want to examine retaining selected rights or income while accessing capital. The proposed retained cash flow, contractual control and transaction costs matter more than a standard percentage recommendation.'
      },
      optionB: {
        description:'A full sale transfers all of the seller\'s interest in the specifically included catalog. Third-party shares, excluded recordings and separately held publishing do not become yours to sell. Payment, licensing powers and continuing obligations are determined by the agreement.',
        pros:[
          'Compare a written offer for the complete interest with a narrower proposal',
          'Collection and administration of the sold interest can be transferred where agreed',
          'Define a boundary between the sold back catalog and excluded future work',
          'Avoid retaining an ownership share in the sold interest, while checking other continuing duties',
          'A buyer can evaluate the complete scope; a premium is not guaranteed',
          'Plan the transaction with independent tax advice before committing',
          'Clarify who makes decisions for the transferred interest after closing'
        ],
        cons:[
          'Future income on the sold interest is no longer yours for the agreed duration',
          'Future growth of that sold interest benefits the buyer',
          'Parting with all of the included interest can be difficult to reverse',
          'The net payment needs to cover your plans without relying on income already sold',
          'Forecasts are uncertain; compare scenarios rather than assuming a peak price',
          'Approval rights may transfer unless protections or exclusions are agreed',
          'There is no automatic right to repurchase because your circumstances change'
        ],
        bestFor:'Owners prepared to consider transferring the complete defined interest after assessing the written price, exclusions, income replacement and continuing obligations. This is not a prediction of a catalog\'s future peak value.'
      },
      features:[
        {feature:'Upfront Capital',optionA:'Price for the specific share or recordings offered',optionB:'Price for all of the defined seller interest'},
        {feature:'Ongoing Revenue',optionA:'Income attributable to retained or excluded interests',optionB:'No income from the sold interest; excluded income can remain'},
        {feature:'Ownership Retained',optionA:'Only the rights explicitly kept outside the transfer',optionB:'No ownership in the transferred interest'},
        {feature:'Future Upside',optionA:'Possible on the retained interest, not guaranteed',optionB:'Passes to buyer on the transferred interest'},
        {feature:'Administrative Complexity',optionA:'Collection, splits and approvals require a clear arrangement',optionB:'Transfer and any continuing duties still need documentation'},
        {feature:'Control',optionA:'Set by the agreement, not percentage alone',optionB:'Set by transferred and reserved rights'},
        {feature:'Flexibility',optionA:'Later sales or repurchase subject to agreed rights and consents',optionB:'No automatic repurchase; check any negotiated provisions'},
        {feature:'Buyer Premium',optionA:'No universal minority discount is established here',optionB:'No universal control premium is established here'}
      ],
      verdict:'Compare a partial offer and a full offer using the same rights schedule, income definition and payment assumptions. Do not presume a minority sale is always better, or that a full sale removes every obligation. List what you keep, what income remains after costs, who controls licensing and what would happen if revenue falls. SPACE can consider a defined share or selected recordings, subject to review and agreement. Use independent advisers and retain the option not to sell.',
      faq:[
        {question:'How does pricing work for a partial sale vs. a full sale?',answer:'A partial offer is negotiated for the actual interest, including its control, duration, restrictions and expected income. It is not necessarily a proportional slice of a full offer. No standard discount, premium or sale multiple is promised. Compare written offers on the same net-income and rights basis.'},
        {question:'Can I buy back the sold portion later?',answer:'Only if the agreement gives you an applicable repurchase right or the owner later agrees to sell. A right of first refusal usually concerns a proposed sale to someone else; it is not automatically an option to buy back whenever you choose. Have an independent lawyer explain the actual clause, trigger, price and time limit.'}
      ]
    }
  },
  {
    family:'personas',slug:'independent-artist-catalog-owner',route:'/for/independent-artist-catalog-owner/',
    patch:{
      metaDescription:'Considering selling an independent music catalog? Define your rights, prepare royalty records and request a free review from SPACE, a direct catalog buyer.',
      description:'An independently released catalog can generate income without a major-label agreement, but distributing your own music does not prove you own every master or composition. Start with the rights and royalty interests you actually control. Your catalog may span one release or years of work, across any genre. If you are exploring a sale, identify the recordings, collaborators, existing agreements and net income before comparing an upfront payment with the income you would retain. SPACE offers a free initial review for a potential direct purchase, not a buyer-listing marketplace.',
      solutions:[
        'A free initial catalog review based on the information and evidence you provide',
        'Educational resources to prepare for the review and understand questions before signing',
        'A conversation with SPACE as a potential direct buyer, rather than a promise of buyer matching',
        'Consideration of selected recordings or a defined share, subject to review and agreement',
        'A clear reminder to obtain independent legal review; SPACE is not your legal adviser',
        'Preparation questions for your own tax adviser, not personalized tax advice from SPACE',
        'No obligation to accept an offer or proceed with a sale'
      ],
      benefits:[
        'Understand which rights and income need to be assessed before an offer can be meaningful',
        'Approach a direct buyer without listing your catalog in an auction',
        'Prepare a documented scope so competing proposals can be compared on a like-for-like basis',
        'Explore full or partial sale scope; SPACE does not offer catalog loans',
        'Clarify which administration duties would transfer and which could remain',
        'Evaluate an actual written offer without treating a scenario calculator as market value',
        'Decide whether to continue, seek independent advice or keep your catalog'
      ],
      caseStudySnippet:'Hypothetical illustration, not a SPACE customer result: an independent owner documents $12,000 in annual net income attributable to the rights being considered. If a transaction covered 50% of that income interest, unchanged future receipts would allocate $6,000 annually to the buyer and leave $6,000 before other costs and taxes. This does not establish a purchase price, predict future receipts or show that such a deal would be suitable or available. The owner would still need a rights schedule, an actual offer and independent advice. No royalty recovery, completed purchase or payout is claimed.',
      ctaText:'Explore a sale of the rights you control',
      faq:[
        {question:'How long does the catalog sale process take?',answer:'SPACE\'s published initial-offer timeframe is typically 5-7 business days after relevant catalog information is received, subject to review. It is not a guaranteed deadline or a payment promise. Closing depends on the agreement, documentation and satisfied transfer conditions.'},
        {question:'What documents do I need to sell my catalog?',answer:'Prepare a track list, royalty statements, a schedule of the interests you control, collaborator splits and relevant distribution, artist, producer and licensing agreements. Flag missing records, outstanding advances and consent requirements. A distributor account or PRO registration alone does not prove every right is transferable.'},
        {question:'What if I am not ready to sell but want to understand my options?',answer:'The initial catalog-review application is free and does not oblige you to sell. The calculator is an assumptions-based scenario, not an appraisal or purchase offer. A potential buyer\'s review is not an independent valuation for tax, estate or litigation purposes.'}
      ]
    }
  }
];

export const sharedCopy = [
  ['SPACE buys music catalogs in ambient, lo-fi, and meditation genres.', 'SPACE considers revenue-generating catalogs across genres. Free initial review; any purchase is subject to assessment and agreement.'],
  ['Submit your catalog and get a valuation from SPACE.', 'Request a free initial review for a potential purchase. No obligation to sell.'],
  ['We work with all kinds of mood and soundscape music creators. Find the approach that fits your situation.', 'We review revenue-generating catalogs from independent artists, producers, labels and owners across genres. Find the preparation guidance that fits your situation.'],
  ["Whether you're an ambient producer, lo-fi beat maker, or meditation composer, learn how SPACE can help you monetize your catalog.", 'Explore catalog-sale preparation for independent artists, producers, labels and owners across genres. Request a free individual review from SPACE.']
];
