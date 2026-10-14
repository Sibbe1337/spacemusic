// Reviewed changes to the immutable September 30 artifact, not a new site build.
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {parse} from '../../services/seller_ui/node_modules/@babel/parser/lib/index.js';
import {sections as sellingSections} from './selling-corrections.mjs';

export const source = 'tmp/growth-preview-v1-20260930';
export const routes = ['guides/music-catalog-valuation-2026/', 'calculator/', 'compare/space-vs-royalty-exchange/', 'guides/how-to-sell-music-rights/', 'blog/independent-record-label-funding-options/'];
export const pages = routes.map(r => r + 'index.html');
const copyright = {source:'US Copyright Office: compositions and sound recordings',url:'https://www.copyright.gov/register/pa-sr.html'};
const nps = {source:'Hipgnosis Songs Fund: 2021 report, glossary definition of NPS',url:'https://www.hipgnosissongs.com/wp-content/uploads/2021/09/210705AnnualReportRNS.pdf'};
const index = {source:'Duetti and Billboard: H2 2026 Music Finance Index (industry-panel perceptions)',url:'https://www.duetti.co/music-finance-index-h2-2026'};
const policy = {source:'SPACE: pricing and offer policy',url:'https://spacemusic.io/pricing.md'};
const auctions = {source:'Royalty Exchange: seller auction process',url:'https://royaltyexchange.com/how-auctions-work-sellers'};
const listings = {source:'Royalty Exchange: Direct Listings announcement (2020)',url:'https://royaltyexchange.com/blog/introducing-direct-listings-giving-artists-more-control-over-their-catalog'};

export function makeEdits(site) {
  const edits = [];
  const module = prefix => {const matches=[...site.active].filter(n=>n.startsWith(prefix)); assert.equal(matches.length,1,prefix); return matches[0];};
  const add = (name,find,replace) => {assert(site.codes.get(name).includes(find),`Missing patch: ${name}: ${find.slice(0,80)}`); edits.push({modules:[name],code:true,find,replace});};
  function object(name,variable,change) {
    const code=site.codes.get(name),ast=parse(code,{sourceType:'module'});
    const decl=ast.program.body.filter(n=>n.type==='VariableDeclaration').flatMap(n=>n.declarations).find(n=>n.id.name===variable);
    assert(decl,variable);
    const old=code.slice(decl.init.start,decl.init.end);
    // Only evaluate a known local data literal, in an empty bounded VM.
    assert(['ObjectExpression','ArrayExpression'].includes(decl.init.type));
    const data=JSON.parse(JSON.stringify(vm.runInNewContext('('+old+')',{}, {timeout:1000})));
    change(data);
    add(name,old,JSON.stringify(data));
  }
  const valuation=module('ValuationGuidePage-reviewed');
  object(valuation,'p',p=>{
    p.tldr="A music catalog is valued from the income a buyer expects the specific rights to generate, adjusted for risk. A simple sale scenario is annual net income x an assumed multiple x the share sold. It is not an offer: the rights, earnings history, costs and transfer conditions need individual review. There is no single multiple that prices every catalog.";
    p.sections[2].heading='Music Catalog Multiples: How to Read the Benchmarks';
    p.sections[2].content=`Published multiples can be useful context, but only if you know what they measure. <a href="${index.url}">Duetti and Billboard's H2 2026 Music Finance Index</a> reports industry-panel perceptions, not a universal price list or a database of independently verified completed sales. For catalogs older than ten years, the panel's average perceived bases were 10.2x for masters and 12.1x for publishing. Those figures do not establish a minimum offer for your catalog.<br/><br/>Before using any benchmark, compare the rights type, catalog age, income definition, reporting period, share acquired and legal term. Do not mix a publisher's net share with gross streaming revenue. Historical institutional acquisition averages are not automatically comparable to a smaller independent catalog.<br/><br/>Genre describes the music, not its price. Ambient, mood, meditation, wellness, lo-fi, nature soundscapes, pop, rock, hip-hop, R&B, country, classical and jazz catalogs all require their own evidence. Use the genre table below as review questions, not a ranking of expected returns. The <a href="/data/music-catalog-deals/">catalog deal tracker</a> separates published transaction information from missing data.`;
    p.sections[1].content += '<br/><br/>To compare two offers, hold the tracks, rights, share, term and income period constant. Then compare the amount payable after disclosed deductions and the income you keep. A larger headline amount for more rights is not automatically a better price. Use the <a href="/blog/music-catalog-offer-checklist/">questions to ask before signing</a> to compare the actual terms.';
    p.citations.push(index,nps);
    p.faq.unshift({question:'How much is a music catalog worth?',answer:'There is no universal amount. Define the rights and reconcile their net income first. Annual net income x an assumed multiple x the share sold gives a hypothetical scenario; an actual offer depends on earnings durability, contracts and the buyer\'s assessment. A stream count, genre or track count alone cannot establish the sale price.'});
  });
  add(valuation,'dateModified:"2026-09-07"','dateModified:"2026-10-08"');
  add(valuation,'Reviewed September 7, 2026.','Updated October 8, 2026.');
  add(valuation,'children:t.tldr})]})','children:t.tldr}),e.jsxs("div",{className:"flex flex-wrap gap-4 mt-4 text-sm",children:[e.jsx(s,{to:"/calculator/",className:"text-brand underline underline-offset-2",children:"Build a hypothetical sale scenario"}),e.jsx("a",{href:"/apply/",className:"text-brand underline underline-offset-2",children:"Request a free catalog review"})]})]})');
  const oldFaq='e.jsx(u,{type:"single",collapsible:!0,className:"w-full",children:t.faq.map((a,i)=>e.jsxs(m,{value:`faq-${i}`,className:"border-b border-black/10",children:[e.jsx(g,{className:"text-base font-medium py-4 hover:no-underline text-left",children:a.question}),e.jsx(h,{className:"text-muted-foreground pb-4 leading-relaxed",children:a.answer})]},i))})';
  add(valuation,oldFaq,'e.jsx("div",{className:"w-full",children:t.faq.map(a=>e.jsxs("details",{className:"border-b border-black/10",children:[e.jsx("summary",{className:"text-base font-medium py-4 text-left cursor-pointer",children:a.question}),e.jsx("p",{className:"text-muted-foreground pb-4 leading-relaxed",children:a.answer})]},a.question))})');

  const selling=module('PillarGuidePage-C957L0vZ');
  object(selling,'k',p=>{
    p.metaDescription='Learn how to sell music rights: verify ownership, prepare royalty statements, compare offers and review the rights, costs and obligations before signing.';
    p.tldr='To sell music rights, define the recordings or compositions and the share you own, reconcile royalty statements, approach suitable buyers and compare written offers for the same scope. Review the contract and transfer requirements before accepting. Selling masters, publishing or a royalty-income interest are different transactions. You can explore a full or partial sale without committing future releases, but exclusions and retained rights must be written into the agreement.';
    p.sections.forEach(s=>{assert(sellingSections[s.id],s.id);s.content=sellingSections[s.id];});
    p.introduction='Selling music rights means exchanging a defined interest and its income for the terms in an agreement. The right starting point is the catalog you control and the evidence behind its earnings, not a celebrity deal or a guessed multiple.\n\nThis guide covers ownership, buyer types, valuation, the sale process, documents, full and partial sales, taxes, preparation, common mistakes and the decision to sell or hold. It is written for independent artists, producers, labels and other catalog owners across genres.\n\nUpdated October 8, 2026. Published by SPACE, a catalog buyer with a commercial interest in acquisitions, not an independent adviser acting for you. This is educational information, not personalized legal, tax or investment advice.';
    const answers=[
      'There is no universal closing time. Evidence checks, consents, negotiation and transfer requirements all matter. SPACE\'s published initial-offer timeframe is typically 5-7 business days after relevant information is received, if the catalog is a fit. An initial offer is not payment, and a marketplace auction period is not its entire closing process.',
      'Possibly. Check ownership separately from the distributor\'s license, exclusivity, assignment restrictions, notice requirements and unrecouped balances. Do not assume a distribution deal is non-exclusive or freely transferable. Obtain any required consents before agreeing to deliver the rights or redirect income.',
      'Net Publisher\'s Share is a publishing-specific measure: publisher receipts after contractual songwriter royalties and the relevant deductions under the stated definition. It is not a universal name for an artist\'s net streaming income or master receipts. Ask the buyer to define its income basis and reconcile that basis to statements before comparing multiples. The Hipgnosis report linked below gives one published NPS definition, not a valuation rule for every catalog.',
      'An independent music lawyer can review scope, reserved rights, warranties, payment conditions and continuing obligations. Requirements and costs vary by jurisdiction and deal. Ask for the review scope and fee in advance; SPACE\'s purchase review is not independent legal advice.',
      'Masters and compositions are separate copyright interests. You can propose a sale of the recording rights you control while excluding publishing, subject to contracts and required consents. More rights sold means a different asset, not necessarily a better price. Specify retained publishing and any approval rights in the agreement.',
      'It depends on the agreement. Specify the existing catalog, a cutoff where relevant and an express exclusion for future work. Check first-refusal provisions, delivery commitments, exclusivity, remixes and alternate versions with an independent adviser. Do not rely on a general promise that new releases are unaffected.',
      'Compare written proposals for the same rights, term, share and income period, including costs, retained income and payment conditions. Published multiples and competing offers are context, not proof of an objectively fair price. SPACE offers a free initial purchase review, not an independent appraisal. You can decline an offer.',
      'Only the income included in the agreement transfers. Define the retained share, cutoff, accrual versus payment dates, collection instructions and treatment of delayed statements or adjustments. Document transitional payments so that neither party mistakes an old-period receipt for income from the new period.'
    ];
    answers.forEach((a,i)=>p.faq[i].answer=a);
    p.citations=[copyright,{source:'US Copyright Office: ownership and transfer',url:'https://www.copyright.gov/title17/92chap2.html'},nps,policy,index,{source:'WIPO: IP valuation methods',url:'https://www.wipo.int/en/web/business/ip-valuation'},{source:'IRS Publication 544: dispositions, classification and self-created works',url:'https://www.irs.gov/publications/p544'},auctions,listings];
    p.spokeLinks.push({slug:'catalog-documents-checklist',title:'Prepare the documents for a catalog sale',url:'/blog/music-catalog-sale-documents-checklist/'},{slug:'catalog-offer-checklist',title:'Compare the terms before signing',url:'/blog/music-catalog-offer-checklist/'},{slug:'label-funding-options',title:'Funding options for an independent label',url:'/blog/independent-record-label-funding-options/'});
  });
  const native='e.jsx("div",{className:"w-full",children:a.faq.map(t=>e.jsxs("details",{className:"border-b border-black/10",children:[e.jsx("summary",{className:"text-base font-medium py-5 text-left cursor-pointer",children:t.question}),e.jsx("p",{className:"text-muted-foreground pb-5 leading-relaxed",children:t.answer})]},t.question))})';
  const sellingFaq='e.jsx(f,{type:"single",collapsible:!0,className:"w-full",children:a.faq.map((t,i)=>e.jsxs(w,{value:`faq-${i}`,className:"border-b border-black/10",children:[e.jsx(b,{className:"text-base font-medium py-5 hover:no-underline text-left",children:t.question}),e.jsx(v,{className:"text-muted-foreground pb-5 leading-relaxed",children:t.answer})]},i))})';
  add(selling,sellingFaq,'(a.slug==="how-to-sell-music-rights"?'+native+':'+sellingFaq+')');
  const plain='e.jsx("p",{className:"text-muted-foreground leading-relaxed whitespace-pre-line max-w-3xl ml-9",children:t.content})';
  const prose='e.jsx("div",{className:"text-muted-foreground leading-relaxed max-w-3xl ml-9",children:t.content.split("\\n\\n").map((paragraph,index)=>e.jsx("p",{className:"mb-6",children:paragraph.split(/(\\*\\*.*?\\*\\*)/g).map((part,key)=>part.startsWith("**")?e.jsx("strong",{children:part.slice(2,-2)},key):part)},index))})';
  add(selling,plain,'(a.slug==="how-to-sell-music-rights"?'+prose+':'+plain+')');
  add(selling,'description:a.metaDescription,url:`https://spacemusic.io/guides/${a.slug}`','description:a.metaDescription,...(a.slug==="how-to-sell-music-rights"?{dateModified:"2026-10-08",citation:a.citations.map(c=>c.url)}:{}),url:`https://spacemusic.io/guides/${a.slug}`');
  add(selling,'children:"Free valuation. No obligation."','children:a.slug==="how-to-sell-music-rights"?"Explore a hypothetical scenario, or request a free purchase review. No obligation.":"Free valuation. No obligation."');

  const comparisonPage=module('CompetitorComparisonPage-primary');
  add(comparisonPage,'children:"Get a free valuation from SPACE. No obligation."','children:s.slug==="space-vs-royalty-exchange"?"Explore a hypothetical scenario, or request a free purchase review. No obligation.":"Get a free valuation from SPACE. No obligation."');

  const comparison=module('competitorComparisonsExpanded-D0DJzCdV');
  object(comparison,'e',rows=>{
    const p=rows.find(p=>p.slug==='space-vs-royalty-exchange'); assert(p);
    p.metaDescription='Compare SPACE with Royalty Exchange: direct review versus a royalty marketplace, listing terms, costs, partial sales and what to check before accepting.';
    p.introduction='Selling a music catalog through a direct buyer and listing royalties on a marketplace are different routes. This comparison is published by SPACE, a buyer, not an independent ranking service. Public sources were checked October 8, 2026; private offers were not tested.';
    p.tldr='SPACE reviews catalog interests directly, across genres, without an auction listing. Royalty Exchange connects royalty owners with investors; its public guides describe auctions and its 2020 Direct Listings announcement describes a non-auction format. Confirm which formats are available for your asset today. Compare written terms for the same rights and income, not a promise that either route always pays more or closes faster.';
    p.spaceProfile.description='SPACE considers revenue-generating catalog rights from artists, producers, labels and catalog owners across genres. The application and initial review are free. An offer is subject to review; payment follows the agreement and transfer requirements. A proposal can concern selected tracks or a defined share, rather than all of your music.';
    p.spaceProfile.strengths=['Direct purchase review without a marketplace listing','Free application and initial review; no listing fee or auction commission','Selected tracks or a defined share can be proposed','No obligation to accept an offer'];
    p.spaceProfile.limitations=['Not every catalog receives an offer','A purchase review is not an independent seller appraisal','Price, retained rights and timing depend on the actual proposal and agreement'];
    p.competitorProfile.description='Royalty Exchange describes a marketplace connecting royalty sellers and investors. Its seller guide covers auction preparation and transfer. Its 2020 Direct Listings announcement also describes offers at a seller-set price without an auction. Ask which format and current terms apply to your specific asset.';
    p.competitorProfile.strengths=['Marketplace access to competing investors','Public guidance on the listing and transfer process','Different royalty interests can be proposed, subject to eligibility','Seller materials cover auction and non-auction approaches'];
    p.competitorProfile.limitations=['Eligibility and current listing options need confirmation','Confirm fees, commitments and withdrawal rules before listing','Neither listing nor investor interest guarantees a completed sale','Documentation and transfer requirements extend beyond a bidding period'];
    p.features=[
      {feature:'Deal type',space:'Direct purchase proposal after review',competitor:'Investor marketplace; confirm available listing format'},
      {feature:'Genre focus',space:'Revenue-generating catalogs across genres; individual review',competitor:'Confirm eligibility for the specific royalty interest'},
      {feature:'Commission / fees',space:'Free application and initial review; no listing fee or auction commission',competitor:'Request current fees and their calculation in the listing agreement'},
      {feature:'Payout speed',space:'Payment follows agreement and satisfied transfer conditions',competitor:'Preparation, bidding where applicable, agreement and transfer are separate stages'},
      {feature:'Partial rights sales',space:'Propose selected tracks or a defined share, subject to review',competitor:'The seller guide describes the ability to specify the royalty interest offered'},
      {feature:'Minimum catalog size',space:'No fixed earnings floor in the cited policy; individual review',competitor:'Confirm current eligibility and evidence requirements'},
      {feature:'Creative control',space:'Define retained rights and approvals in writing',competitor:'Define retained rights and approvals in writing'},
      {feature:'Process complexity',space:'Application, evidence review, proposal, agreement and transfer',competitor:'Evidence review, listing agreement, sale process and transfer'},
      {feature:'Valuation approach',space:'Individual assessment of the defined rights and earnings',competitor:'Investor offers under the applicable listing terms'},
      {feature:'Track record',space:'No acquisition-volume claim made in this comparison',competitor:'Assess relevant completed listings, not headline platform totals alone'}
    ];
    p.verdict='Choose which process to explore based on the rights you can offer and the commitments you accept. A direct review avoids listing your asset at auction; a marketplace exposes an eligible interest to investor offers. Neither model proves a higher net price. Compare the retained income, net proceeds, legal term and closing conditions, and obtain independent advice before accepting.';
    p.bestFor={space:'Owners across genres exploring a free direct-purchase review for defined catalog interests.',competitor:'Owners considering investor price discovery and willing to review listing commitments.'};
    p.faq[0].answer='Royalty Exchange describes itself as a marketplace connecting sellers and investors. Its Direct Listings announcement describes a non-auction listing format, not a promise that the platform itself buys your catalog. Confirm the purchaser and current sale format in the documents.';
    p.faq[1].answer='You can propose a defined share of the rights you control or selected tracks for individual review. Specify what transfers, what stays with you, and any required consents. A partial sale is not a guarantee of unchanged creative control or a particular offer.';
    p.faq[2].answer='Its seller guide describes a bidding phase of usually less than one week after an opening bid triggers the auction. Preparation and transfer are separate stages. Ask for the timetable and conditions for your transaction; an auction duration is not a payment deadline.';
    p.sections=[{title:'Compare the same deal before comparing the price',paragraphs:['Request two proposals for the same track list, rights, share, territory, term and reporting period. A price for all masters cannot be compared directly with a price for a limited publishing-income interest.'],items:['Confirm the purchaser and exactly what you are committing to before listing or accepting.','Reconcile the headline amount to the cash payable after fees, balances and closing conditions.','Write down the income, approvals and future works you retain.','Confirm accounting duties, transition receipts and what happens if closing is delayed.'],links:[{label:'Questions to ask before signing an offer',url:'/blog/music-catalog-offer-checklist/'},{label:'Prepare the rights and royalty documents',url:'/blog/music-catalog-sale-documents-checklist/'}]}];
    p.citations=[auctions,listings,policy];
  });

  const funding=module('BlogPost-article-authentic-c9f7be5415ee');
  object(funding,'article',a=>{
    a.introduction='<p><strong>How can an independent record label fund its next release?</strong> Start by separating an existing-catalog sale, an advance against future receipts and a loan. Each commits different rights, income or repayment obligations. If you have an earning catalog and want to explore selling a defined interest, SPACE offers a free individual purchase review. SPACE does not offer a label loan or royalty advance.</p>\n'+a.introduction;
    const block='<h2 id="which-funding-route-fits-your-label">Which route fits your label?</h2><ul><li><strong>Existing catalog income, willing to sell a defined interest:</strong> prepare statements and ownership records for a purchase review. Check the income left to pay artists and operate the label.</li><li><strong>Want to keep ownership but commit future receipts:</strong> compare an advance provider\'s term, recoupment and new-release obligations. Retaining ownership does not mean retaining all income.</li><li><strong>Need a loan or have no earning catalog yet:</strong> research lenders, grants or other funding with criteria relevant to your country and project. This page does not establish eligibility, and a SPACE review is not a loan application.</li></ul><p>For the purchase route, <a href="/apply/">request a free review of the catalog interest your label controls</a>. For the sale process itself, read <a href="/guides/how-to-sell-music-rights/">how a music-rights sale works</a>.</p>\n';
    a.body=block+a.body.replace('Reviewed September 16, 2026.','Updated October 8, 2026.');
    a.headings.unshift({id:'which-funding-route-fits-your-label',text:'Which route fits your label?'});
    a.dateModified='2026-10-08';
    a.schema.find(s=>s['@type']==='BlogPosting').dateModified=a.dateModified;
    // Omit an outdated optional word count rather than publish stale metadata.
    delete a.schema.find(s=>s['@type']==='BlogPosting').wordCount;
  });
  const calc=module('Calculator-scenario');
  add(calc,"A catalog's sale value is usually its annual net royalties multiplied by a multiple the buyer assumes. Use documented net income to explore a hypothetical sale, or request an individual review if you do not know which assumptions to use. This calculator does not estimate a market multiple or produce a SPACE offer.","Explore a hypothetical music catalog sale: monthly net income x 12 x your assumed multiple x the share sold. Use income attributable to the rights you can offer. No multiple is supplied, and the result is not a valuation or a SPACE offer. If you do not know the assumptions, you can request a free review without them.");
  add(calc,' Start with your email and artist or label name using the free-review button above. SPACE requests the relevant income and rights documents privately by email and assesses each catalog individually. Submitting the form requests a review, not a sale.',' The guided application asks about your role, rights and any royalty income you know. Unknown income is welcome; no guessed multiple or document is needed to start. SPACE follows up privately for relevant evidence. Submitting requests a review, not a sale.');
  return edits;
}
