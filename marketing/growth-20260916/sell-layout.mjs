import assert from 'node:assert/strict';

// Move the reviewed page's existing content, rather than maintaining a second copy.
export function layoutSellPage(doc) {
  const main = doc.querySelector('main');
  const hero = main.previousElementSibling;
  const [overview, ...sections] = [...main.children];
  const cta = sections.pop();
  assert.equal(sections.length, 3, 'Expected three existing genre groups');
  assert.equal(hero.querySelector('h1').textContent, 'What genre do you make?');
  main.id = 'space-growth-sell';
  main.tabIndex = -1;
  main.className = 'flex-grow';
  const create = (tag, className, text) => {
    const element = doc.createElement(tag);
    element.className = className;
    if (text) element.textContent = text;
    return element;
  };
  const link = (href, text, className) => {
    const element = create('a', className, text);
    element.href = href;
    return element;
  };
  const retag = (element, tag, className) => {
    const replacement = create(tag, className);
    replacement.append(...element.childNodes);
    element.replaceWith(replacement);
    return replacement;
  };

  const heroCopy = hero.firstElementChild;
  hero.className = 'sell-hero';
  heroCopy.className = 'sell-hero-copy';
  heroCopy.children[0].className = 'sell-kicker';
  heroCopy.querySelector('h1').className = 'sell-title';
  heroCopy.children[2].className = 'sell-intro';
  const actions = create('div', 'sell-actions');
  actions.append(
    link('/apply/', 'Request a free catalog review', 'sell-primary'),
    link('#sell-directory', 'Explore the genre guides', 'sell-secondary'),
  );
  heroCopy.append(actions);

  const overviewBody = overview.firstElementChild;
  const [eyebrow, heading, explanation, clusters] = [...overviewBody.children];
  const review = create('aside', 'sell-review');
  review.setAttribute('aria-labelledby', 'sell-review-title');
  eyebrow.className = 'sell-kicker';
  heading.id = 'sell-review-title';
  heading.className = 'sell-review-title';
  explanation.className = 'sell-review-description';
  review.append(eyebrow, heading, explanation);
  const heroLayout = create('div', 'sell-container sell-hero-layout');
  heroLayout.append(heroCopy, review);
  hero.append(heroLayout);

  const directory = create('div', 'sell-directory');
  directory.id = 'sell-directory';
  const jumpNav = create('nav', 'sell-jump');
  jumpNav.setAttribute('aria-label', 'Genre guide groups');
  const jumpBody = create('div', 'sell-container sell-jump-layout');
  jumpBody.append(create('p', 'sell-kicker', 'Browse catalog guides'));
  const jumpLinks = create('div', 'sell-jump-links');
  jumpBody.append(jumpLinks);
  jumpNav.append(jumpBody);
  directory.append(jumpNav);
  const groupIDs = ['commercial-genres', 'mood-functional-genres', 'specialized-genres'];
  const groupLabels = ['Commercial', 'Mood & functional', 'Specialized'];
  sections.forEach((section, index) => {
    section.className = 'sell-group';
    section.id = groupIDs[index];
    section.setAttribute('aria-labelledby', `${groupIDs[index]}-title`);
    const container = section.firstElementChild;
    container.className = 'sell-container sell-group-layout';
    const [label, grid] = [...container.children];
    const heading = retag(label, 'h2', 'sell-group-title');
    heading.id = `${groupIDs[index]}-title`;
    const groupIntro = create('div', 'sell-group-intro');
    groupIntro.append(create('p', 'sell-group-number', `0${index + 1}`), heading);
    groupIntro.append(create('p', 'sell-group-count', `${grid.children.length} guides`));
    container.prepend(groupIntro);
    grid.className = 'sell-guide-list';
    for (const guide of grid.children) {
      guide.className = 'sell-guide';
      guide.querySelector(':scope>p').className = 'sell-guide-genre';
      retag(guide.querySelector('h2'), 'h3', 'sell-guide-title');
      const description = guide.querySelector('h3').nextElementSibling;
      description.className = 'sell-guide-description';
      for (const paragraph of [...guide.querySelectorAll(':scope>p')].slice(2)) {
        paragraph.className = 'sell-guide-detail';
        paragraph.querySelector('span')?.removeAttribute('class');
      }
      const end = guide.lastElementChild;
      end.className = 'sell-guide-end';
      end.firstElementChild.removeAttribute('class');
      const arrow = end.querySelector('svg');
      arrow.removeAttribute('class');
      arrow.setAttribute('aria-hidden', 'true');
      arrow.setAttribute('focusable', 'false');
    }
    jumpLinks.append(link(`#${section.id}`, groupLabels[index], 'sell-jump-link'));
    directory.append(section);
  });

  overview.className = 'sell-clusters';
  overview.id = 'subgenre-overview';
  overview.setAttribute('aria-labelledby', 'sell-clusters-title');
  overviewBody.className = 'sell-container';
  const clusterHeading = create('h2', 'sell-section-title', 'Explore the subgenres.');
  clusterHeading.id = 'sell-clusters-title';
  overviewBody.prepend(clusterHeading);
  clusters.className = 'sell-cluster-list';
  for (const cluster of clusters.children) {
    cluster.className = 'sell-cluster';
    retag(cluster.firstElementChild, 'h3', 'sell-cluster-title');
    for (const paragraph of cluster.querySelectorAll(':scope>p')) paragraph.className = 'sell-cluster-description';
    cluster.querySelector(':scope>p:last-of-type').className = 'sell-cluster-note';
    cluster.querySelector('div').className = 'sell-cluster-links';
    for (const anchor of cluster.querySelectorAll('a')) anchor.className = 'sell-subgenre';
  }
  jumpLinks.append(link('#subgenre-overview', 'Subgenre overview', 'sell-jump-link'));

  cta.className = 'sell-final';
  const ctaBody = cta.firstElementChild;
  ctaBody.className = 'sell-container sell-final-layout';
  const ctaCopy = create('div', 'sell-final-copy');
  const [ctaHeading, ctaDescription, ctaActions] = [...ctaBody.children];
  ctaHeading.className = 'sell-section-title';
  ctaDescription.className = 'sell-final-description';
  ctaCopy.append(ctaHeading, ctaDescription);
  ctaActions.className = 'sell-actions';
  ctaActions.querySelector('[href="/apply/"]').className = 'sell-primary';
  ctaActions.querySelector('[href="/calculator/"]').className = 'sell-secondary';
  ctaActions.prepend(ctaActions.querySelector('[href="/apply/"]'));
  ctaBody.prepend(ctaCopy);
  main.replaceChildren(hero, directory, overview, cta);
  doc.querySelector('#root').prepend(link('#space-growth-sell', 'Skip to main content', 'space-skip'));
  return main;
}
