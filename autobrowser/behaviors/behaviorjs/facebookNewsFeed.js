// TODO(n0tan3rd): Expand comments and view them like twitter
(function viewNewsFeedSetup(xpg, debug = false) {
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

  /**
   * @desc This xpath query is based on the fact that the first item in a FB news feed
   * is fixed and all other feed items are lazily loaded.  Each lazily loaded feed item
   * has `id="hyperfeed_story_id_5b90323a90ce80648983726"` but we do not care about
   * the `_[a-z0-9]+` portion of it. Like how we handle twitter feeds, a visited it is
   * marked by adding `$wrvisited$` to its classList so we look for elements with ids
   * starting with `hyperfeed_story_id` and their classList does not contain `$wrvisited$`
   * @type {string}
   */
  const feedItemSelector =
    '//div[starts-with(@id,"hyperfeed_story_id") and not(contains(@class, "$wrvistited$"))]';

  const delay = (delayTime = 3000) =>
    new Promise(r => setTimeout(r, delayTime));

  function scrollIntoView(elem, delayTime = 2500) {
    elem.scrollIntoView({
      behavior: 'auto',
      block: 'center',
      inline: 'center'
    });
    return delay(delayTime);
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
    return delay(delayTime);
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

  /**
   * @desc See description for {@link getFeedItems}
   * @param {HTMLElement} elem - The current
   * @returns {boolean}
   */
  const newsFeedItemFilter = elem => elem.offsetTop !== 0;

  /**
   * @desc facebook hides upcoming feed story element. when it is time to display
   * the story, the content is fetched and the element is unhidden.
   * Need to filter these elements out so we do not mark them as visited when
   * they are hidden (have width, height = 0 && offsetTop = 0)
   * @param {function (string, HTMLElement?): Array<HTMLElement>} xpathG
   * @return {Array<HTMLElement>}
   */
  const getFeedItems = (xpathG) => xpathG(feedItemSelector).filter(newsFeedItemFilter);

  /**
   * @desc Views each entry in a FB news.
   * (S1) Build initial set of to be feed items
   * (S2) For each feed item visible at current scroll position:
   *      - mark as visited
   *      - scroll into view
   *      - yield feed item
   * (S3) Once all feed items at pager set have been visited:
   *      - wait for FB to load more feed items (if any more are to be had)
   *      - if FB has added more feed items add them to the to be visited set
   * (S4) If we have more feed items to visit and can scroll more:
   *      - GOTO S2
   * @param {function (string, HTMLElement?): Array<HTMLElement>} xpathG
   * @returns {AsyncIterator<HTMLElement>}
   */
  async function* newsFeedIterator(xpathG) {
    let feedItems = getFeedItems(xpathG);
    let feedItem;
    do {
      while (feedItems.length > 0) {
        feedItem = feedItems.shift();
        if (window.$WRSTP$) return;
        await scrollIt(feedItem);
        feedItem.classList.add('$wrvistited$');
        yield feedItem;
      }
      if (window.$WRSTP$) return;
      feedItems = getFeedItems(xpathG);
      if (feedItems.length === 0) {
        await delay();
        feedItems = getFeedItems(xpathG);
      }
      if (window.$WRSTP$) return;
    } while (feedItems.length > 0 && canScrollMore());
  }

  window.$WRNFIterator$ = newsFeedIterator(xpg);
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRNFIterator$.next();
    return next.done;
  };
})($x, true);
