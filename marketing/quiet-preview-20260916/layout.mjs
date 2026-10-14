import assert from 'node:assert/strict';

export function quietHomeLayout(document) {
  const main = document.querySelector('#space-growth-home');
  assert(main, 'Build on the current growth preview, not a historical website');
  const sections = [...main.children];
  assert.equal(sections.length, 9);
  const create = (tag, className) => {
    const node = document.createElement(tag);
    node.className = className;
    return node;
  };
  sections[0].classList.add('quiet-hero');
  const review = sections[0].querySelector('.growth-review');
  const [label, heading, description, definitions, link] = [...review.children];
  const rows = [...definitions.children];
  assert.equal(rows.length, 3);
  const bento = create('section', 'quiet-bento');
  bento.setAttribute('aria-label', 'What a catalog review covers');
  const grid = create('div', 'quiet-bento-grid');
  const introduction = create('div', 'quiet-bento-intro');
  introduction.append(label, heading, description, link);
  const evidence = create('dl', 'quiet-bento-evidence');
  evidence.append(rows[0], rows[1]);
  const decision = create('dl', 'quiet-bento-decision');
  decision.append(rows[2]);
  grid.append(introduction, evidence, decision);
  bento.append(grid);
  review.remove();
  sections[0].after(bento);
  for (const [index,name] of [[1,'quiet-facts'],[2,'quiet-answers'],[3,'quiet-comparison'],[4,'quiet-process'],[5,'quiet-genres'],[6,'quiet-calculator'],[7,'quiet-faq'],[8,'quiet-close']]) sections[index].classList.add(name);
  const genres = sections[5];
  genres.id = 'catalog-genres';
  const container = genres.firstElementChild;
  const [eyebrow, genreHeading, genreIntro, expansion, audience, directory, allGenres] = [...container.children];
  assert.equal(directory.children.length, 9, 'Keep all nine existing genre destinations');
  const genreLayout = create('div', 'quiet-genre-layout');
  const genreIntroduction = create('div', 'quiet-genre-introduction');
  const genreLinks = create('div', 'quiet-genre-links');
  genreHeading.id = 'catalog-genres-title';
  genres.setAttribute('aria-labelledby', genreHeading.id);
  directory.className = 'quiet-genre-directory';
  allGenres.className = 'quiet-genre-all';
  const individualReview = audience.querySelector('a[href="/apply/"]');
  assert(individualReview, 'Preserve the individual review route');
  individualReview.classList.add('quiet-genre-review');
  genreIntroduction.append(eyebrow, genreHeading, genreIntro, expansion, individualReview);
  for (const link of directory.children) {
    link.className = 'quiet-genre-link';
    const headingRow = link.firstElementChild;
    headingRow.className = 'quiet-genre-name';
    headingRow.querySelector('span').className = 'quiet-genre-action';
  }
  genreLinks.append(directory, allGenres);
  genreLayout.append(genreIntroduction, genreLinks);
  container.replaceChildren(genreLayout, audience);
  return main;
}
