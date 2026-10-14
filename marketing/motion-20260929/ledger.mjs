// Idea 2, v3: animate the existing comparison table instead of adding a chart.
// As the table scrolls into view, the "Keep streaming" column fades back and each
// "Sell to SPACE" row lights up in turn (a faint brand tint and a small dot).
// No new text or elements, only this style block. Without scroll-driven animation
// support, or with reduced motion, the table is exactly the production table.
const rows = [2, 3, 4, 5, 6].map((n, i) => {
  const s = 22 + i * 6;
  return `.quiet-comparison .rounded-2xl>.grid:nth-child(${n})>*{animation-range:cover ${s}% cover ${s + 10}%}`;
}).join('\n');

const css = `@supports (animation-timeline:view()){@media (prefers-reduced-motion:no-preference){
.quiet-comparison .rounded-2xl{view-timeline:--motion-comparison block}
.quiet-comparison .rounded-2xl>.grid:not(:first-child)>*{animation-timeline:--motion-comparison;animation-fill-mode:both;animation-timing-function:ease-out}
.quiet-comparison .rounded-2xl>.grid:not(:first-child)>:nth-child(2){animation-name:motion-comparison-fade}
.quiet-comparison .rounded-2xl>.grid:not(:first-child)>:nth-child(3){position:relative;isolation:isolate}
.quiet-comparison .rounded-2xl>.grid:not(:first-child)>:nth-child(3)::before{content:"";position:absolute;inset:0;z-index:-1;background:var(--color-brand);opacity:0;animation:inherit;animation-name:motion-comparison-tint}
.quiet-comparison .rounded-2xl>.grid:not(:first-child)>:nth-child(3)::after{content:"";position:absolute;left:.5rem;top:calc(1rem + .75em);width:5px;height:5px;margin-top:-2.5px;border-radius:50%;background:var(--color-brand);transform:scale(0);animation:inherit;animation-name:motion-comparison-dot}
${rows}
@media (max-width:767px){.quiet-comparison .rounded-2xl>.grid:not(:first-child)>:nth-child(3)::after{display:none}}
}}
@keyframes motion-comparison-fade{from{opacity:1}to{opacity:.45}}
@keyframes motion-comparison-tint{from{opacity:0}to{opacity:.05}}
@keyframes motion-comparison-dot{from{transform:scale(0)}to{transform:scale(1)}}`;

export const ledger = `<style id="motion-comparison">${css}</style>`;
