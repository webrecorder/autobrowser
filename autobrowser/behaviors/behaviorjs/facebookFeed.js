/*
  WIP
  Facebook populates its story feed with zero offsetTop elements that match our xpath query (not visible elements)
  We get stuck at the bottom sometimes (only zero offsetTops) and need manual scrolling??????
 */
(async function viewFeed(xpg, debug = false) {
    if (
    typeof xpg !== 'function' ||
    xpg.toString().indexOf('[Command Line API]') === -1
  ) {
    /**
     * @desc Polyfill console api $x
     * @param {string} xpathQuery
     * @param {Element | Document} startElem
     * @return {Array<HTMLElement>}
     */
    xpg = function(xpathQuery, startElem) {
      if (startElem == null) {
        startElem = document;
      }
      const snapShot = document.evaluate(
        xpathQuery,
        startElem,
        null,
        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
        null
      );
      const elements = [];
      let i = 0;
      let len = snapShot.snapshotLength;
      while (i < len) {
        elements.push(snapShot.snapshotItem(i));
        i += 1;
      }
      return elements;
    };
  }

  if (document.getElementById('$wrStyle$') == null) {
    const style = document.createElement('style');
    style.id = '$wrStyle$';
    style.innerText = 'body, .wr-scroll-container { scroll-behavior: smooth }';
    document.head.appendChild(style);
  }

  const canScrollMore = () =>
    window.scrollY + window.innerHeight <
    Math.max(
    document.body.scrollHeight,
    document.body.offsetHeight,
    document.documentElement.clientHeight,
    document.documentElement.scrollHeight,
    document.documentElement.offsetHeight
  );

  const timelineSelector =
    '//div[starts-with(@id,"hyperfeed_story_id") and not(contains(@class, "$wrvistited$"))]';

  function scrollIntoView(elem, delayTime = 2500) {
    elem.scrollIntoView({
      behavior: 'auto',
      block: 'center',
      inline: 'center'
    });
    return new Promise(r => setTimeout(r, delayTime));
  }

  function scrollIt(elem, delayTime = 2500) {
    if (elem.offsetTop === 0) {
      return scrollIntoView(elem, delayTime);
    }
    window.scrollTo({
      behavior: 'smooth',
      left: 0,
      top: elem.offsetTop
    });
    return new Promise(r => setTimeout(r, delayTime));
  }

  function loadDelay(delayTime = 3000) {
    return new Promise(r => setTimeout(r, delayTime));
  }

  async function timelineIterator(xpg) {
    let feedItems = xpg(timelineSelector);
    let feedItem;
    do {
      while (feedItems.length > 0) {
        feedItem = feedItems.shift();
        feedItem.classList.add('$wrvistited$');
        console.log(feedItem);
        console.log(feedItem.id);
        console.log(feedItem.offsetTop);
        await scrollIt(feedItem);
      }
      feedItems = xpg(timelineSelector);
      if (feedItems.length === 0) {
        await loadDelay();
        feedItems = xpg(timelineSelector);
      }
    } while (feedItems.length > 0 && canScrollMore());
    console.log('done');
  }

  timelineIterator(xpg).catch(error => console.error(error));
})($x, true);
