// TODO(n0tan3rd): Expand comments and view them like twitter
// TODO(n0tan3rd): Need better scrolling here
(function viewNewsFeedSetup(xpg, debug = false) {
  if (document.getElementById('$wrStyle$') == null) {
  const style = document.createElement('style');
  style.id = '$wrStyle$';
  style.innerText = 'body, .wr-scroll-container { scroll-behavior: smooth }';
  document.head.appendChild(style);
}

var canScrollMore = () =>
  window.scrollY + window.innerHeight <
  Math.max(
    document.body.scrollHeight,
    document.body.offsetHeight,
    document.documentElement.clientHeight,
    document.documentElement.scrollHeight,
    document.documentElement.offsetHeight
  );

var userTimelineSelector =
  '//div[contains(@class, "userContentWrapper") and not(contains(@class, "wrvistited"))]';

var delay = (delayTime = 3000) => new Promise(r => setTimeout(r, delayTime));

function scrollIntoView(elem, delayTime = 2500) {
  elem.scrollIntoView({
    behavior: 'auto',
    block: 'center',
    inline: 'center'
  });
  return delay(delayTime);
}
function scrollDownByElemHeight(elem) {
  if (!elem) return;
  let rect = elem.getBoundingClientRect();
  window.scrollBy(0, rect.height + elem.offsetHeight);
}

async function* timelineIterator(xpg) {
  let timelineItems = xpg(userTimelineSelector);
  let tlItem;
  do {
    while (timelineItems.length > 0) {
      tlItem = timelineItems.shift();
      if (window.$WRSTP$) return;
      await scrollIntoView(tlItem);
      tlItem.classList.add('wrvistited');
      yield tlItem;
    }
    if (window.$WRSTP$) return;
    timelineItems = xpg(userTimelineSelector);
    if (timelineItems.length === 0) {
      scrollDownByElemHeight(tlItem);
      await delay();
      timelineItems = xpg(userTimelineSelector);
    }
    if (window.$WRSTP$) return;
  } while (timelineItems.length > 0 && canScrollMore());
}

window.$WRTLIterator$ = timelineIterator(xpg);
window.$WRIteratorHandler$ = async function() {
    const next = await $WRTLIterator$.next();
    return next.done;
};

})($x, true);
