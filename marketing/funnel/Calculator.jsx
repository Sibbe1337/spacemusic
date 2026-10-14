import { r as React, e as jsxRuntime } from './vendor-DhPEFgb5.js';
import { N as Navbar } from './Navbar-DK5bZPep.js';
import { F as Footer } from './Footer-CiCbq8u0.js';
import { S as SEOHead } from './SEOHead-C4J8_WVH.js';
import { scenario, netFromReceipts } from './scenario.mjs';

const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
const inputClass = 'mt-1.5 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-ink';
const faqs = [
  ['How is my catalog valued?', 'An individual review considers documented income, the rights you can transfer, contracts and the risks attached to future earnings. This tool only calculates the assumptions you enter. It does not supply a market multiple or a SPACE offer.'],
  ["What does the 'share to sell' slider mean?", 'It is the percentage of the defined rights and income represented by your inputs that you would sell, not automatically a percentage of every right in every recording and composition. A partial sale may be possible, subject to ownership and agreement.'],
  ['How quickly will I get paid?', 'SPACE typically provides an initial offer within 5-7 business days after receiving the relevant information, if the catalog is a fit. Payment is by bank transfer after the agreement is complete and transfer conditions are satisfied. The calculator does not promise a payment date.'],
  ['Can I sell only specific tracks?', 'You can propose specific tracks, albums or a share of defined rights for review. The transferable scope, retained rights and any consent requirements must be confirmed before a sale.']
];

export default function Calculator() {
  const [mode, setMode] = React.useState('direct');
  const [monthly, setMonthly] = React.useState('');
  const [receipts, setReceipts] = React.useState('');
  const [payouts, setPayouts] = React.useState('');
  const [costs, setCosts] = React.useState('');
  const [multiple, setMultiple] = React.useState('');
  const [share, setShare] = React.useState('70');
  const net = mode === 'direct' ? monthly : netFromReceipts(receipts, payouts, costs);
  const result = scenario(net, multiple, share);
  React.useEffect(() => {
    if (result) { try { window.spaceFunnel?.once('calculator_used'); } catch {} }
  }, [Boolean(result)]);
  const field = (label, value, update, props = {}) => <label className="block text-sm text-ink-muted mb-6">{label}<input className={inputClass} type="number" inputMode="decimal" min="0" step="any" value={value} onChange={event => update(event.target.value)} {...props} /></label>;
  const ctaClass = 'inline-flex items-center justify-center gap-2 bg-brand text-white font-medium px-8 py-3.5 text-base rounded-full hover:bg-brand-hover transition-colors';
  return <div className="min-h-screen flex flex-col bg-cream">
    <SEOHead title="Music Catalog Value Calculator: Build a Sale Scenario" description="Calculate a hypothetical catalog sale from monthly net income, your assumed multiple and the share sold. Request a free individual catalog review." canonical="/calculator/" />
    <Navbar />
    <section className="pt-28 pb-12 md:pt-36 md:pb-14"><div className="max-w-4xl mx-auto px-6 text-center">
      <p className="text-xs font-normal tracking-[0.25em] text-ink-faint uppercase mb-6">Free tool</p>
      <h1 className="font-display text-4xl md:text-6xl tracking-tight text-ink leading-[1.05] mb-4">How much could your music catalog sell for?</h1>
      <p className="text-sm md:text-base text-ink-muted font-normal max-w-2xl mx-auto leading-relaxed">Use documented net income to explore a hypothetical sale, or request an individual review if you do not know which assumptions to use. This calculator does not estimate a market multiple or produce a SPACE offer.</p>
    </div></section>
    <section className="pb-20"><div className="max-w-6xl mx-auto px-6 grid lg:grid-cols-[1.1fr_0.9fr] gap-6 lg:gap-8 items-start">
      <div className="bg-white border border-black/10 rounded-3xl p-6 md:p-8">
        <p className="text-xs uppercase tracking-[0.18em] text-ink-faint mb-3">Scenario inputs (USD)</p>
        <div className="flex flex-wrap gap-2 mb-8">{[['direct', 'Enter monthly net income'], ['derived', 'Calculate net income from receipts']].map(([value, label]) => <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)} className={`px-3 py-1.5 rounded-full text-xs border ${mode === value ? 'bg-brand-light text-ink border-brand/30' : 'bg-white text-ink-muted border-black/10'}`}>{label}</button>)}</div>
        {mode === 'direct' ? field('Monthly net income (USD)', monthly, setMonthly) : <>
          {field('Monthly receipts before payouts and costs (USD)', receipts, setReceipts)}
          {field('Artist royalty payout (%)', payouts, setPayouts, { max: 100 })}
          {field('Operating costs (%)', costs, setCosts, { max: 100 })}
          <p className="text-xs text-ink-muted mb-6">Use percentages of those same receipts. Combined deductions cannot exceed 100%. {net !== null && <>Calculated monthly net income: {money(net)}.</>}</p>
        </>}
        {field('Assumed annual-income multiple', multiple, setMultiple, { 'aria-describedby': 'multiple-help' })}
        <p id="multiple-help" className="text-xs text-ink-muted mb-8">Choose a positive multiple only to explore an assumption. No market multiple is supplied. Don't know what to enter? You can leave it blank and use the Request a free catalog review button; no multiple is needed to apply. A multiple is not the legal term of a sale or another number of years to multiply.</p>
        {field('Share of defined rights to sell (%)', share, setShare, { max: 100, 'aria-describedby': 'share-help' })}
        <input type="range" aria-label="Adjust share to sell" min="0" max="100" step="1" value={share === '' ? 0 : share} onChange={event => setShare(event.target.value)} className="w-full" />
        <p id="share-help" className="text-xs text-ink-muted mt-3">Use 0-100% of the rights represented by your net income. Do not subtract the sold share from the income first; the formula applies it once.</p>
      </div>
      <aside className="lg:sticky lg:top-24 bg-dark rounded-3xl p-6 md:p-8 text-white border border-white/10">
        <h2 className="text-sm uppercase tracking-[0.2em] text-white/75 mb-4">Hypothetical sale scenario</h2>
        <div role="status" aria-live="polite" aria-atomic="true" className="mb-6" data-scenario-result>
          {result ? <><p className="text-4xl md:text-5xl font-semibold tabular-nums tracking-tight leading-[1.1]" style={{ overflowWrap: 'anywhere' }}>{money(result.total)}</p><p className="text-sm text-white/80 mt-3">{money(Number(net))} per month x 12 x {multiple} x {share}%</p></> : <p className="text-base text-white/80">Enter valid income, a positive assumed multiple and a share from 0-100% to see a scenario. Zero income is allowed.</p>}
        </div>
        <p className="text-sm text-white/80 mb-7">Not a market value, guaranteed price or SPACE offer. This arithmetic does not price risk, taxes, fees, recoupment or transfer conditions.</p>
        <a href="/apply/" className={`${ctaClass} w-full`}>Request a free catalog review</a>
        <p className="text-xs text-white/80 text-center mt-3">Free evaluation. No obligation.</p>
        <div className="mt-7 pt-6 border-t border-white/10">
          <h3 className="text-sm mb-3">From an assumption to a useful next step</h3>
          <p className="text-sm text-white/80 leading-relaxed mb-4">Monthly net income x 12 x assumed annual-income multiple x share sold = your hypothetical scenario. There is no additional years multiplier or predicted price range.</p>
          <p className="text-sm text-white/80 leading-relaxed mb-4">For example, $1,000 a month x 12 x an arbitrary 4 x 50% gives $24,000. The 4 is an illustration, not a market benchmark or an offer. If the income already represents only your owned interest, the percentage you sell applies to that interest once, not to the entire catalog again.</p>
          <p className="text-sm text-white/80 leading-relaxed mb-4"><strong>Don't know a multiple? You do not need one to request a review.</strong> Start with your email and artist or label name using the free-review button above. SPACE requests the relevant income and rights documents privately by email and assesses each catalog individually. Submitting the form requests a review, not a sale.</p>
          <p className="text-sm text-white/80 leading-relaxed">A scenario is also not cash in your bank account. Taxes, transaction costs, outstanding balances and payment conditions need separate consideration before accepting an offer.</p>
        </div>
      </aside>
    </div></section>
    <section className="border-t border-black/10 py-20"><div className="max-w-3xl mx-auto px-6 text-sm text-ink-muted leading-relaxed">
      <h2 className="font-display text-3xl text-ink mb-6">Gross revenue, net income and the rights sold</h2>
      <p className="mb-4">Gross revenue is before relevant deductions. Distributor receipts may already exclude some fees. Net income here means the income attributable to the defined rights after applicable distributor fees, third-party royalty payouts and operating costs. Avoid deducting an expense twice, and use one currency and a representative period.</p>
      <p className="mb-4">Use the <a className="underline text-ink" href="/blog/music-catalog-sale-documents-checklist/">seller's document checklist</a> to organize the statements and agreements behind this figure.</p>
      <p className="mb-4">Sound recording rights and composition rights are distinct. Only include income attributable to rights you own and can transfer. Selling part of your share is not the same as selling that percentage of the entire catalog. Outstanding advances, co-owner permissions and existing agreements need a separate review.</p>
      <p>Read the <a className="underline text-ink" href="/guides/music-catalog-valuation-2026/">music catalog valuation guide</a> for the factors beyond this calculation.</p>
    </div></section>
    <section className="border-t border-black/10 py-20"><div className="max-w-xl mx-auto px-6"><h2 className="text-xs tracking-[0.2em] text-ink-faint uppercase mb-10">Questions</h2>{faqs.map(([question, answer]) => <details key={question} className="border-b border-black/10"><summary className="text-sm text-ink py-5 cursor-pointer">{question}</summary><p className="text-sm text-ink-muted pb-5 leading-relaxed">{answer}</p>{question === 'How quickly will I get paid?' && <p className="text-sm text-ink-muted pb-5 leading-relaxed">Read the <a className="underline text-ink" href="/pricing.md">review and payment conditions</a> before treating an expected offer date as a closing date.</p>}</details>)}</div></section>
    <section className="border-t border-black/10 bg-dark py-24 md:py-32"><div className="max-w-3xl mx-auto px-6 text-center"><h2 className="text-3xl md:text-5xl font-display font-semibold tracking-tight text-white mb-6">Ready for an individual review?</h2><p className="text-white/82 mb-10">If your catalog is a fit, an initial offer typically follows within 5-7 business days after we receive the relevant information. Payment follows the completed agreement and satisfied transfer conditions.</p><a href="/apply/" className={ctaClass}>Request a free catalog review</a></div></section>
    <Footer />
  </div>;
}
