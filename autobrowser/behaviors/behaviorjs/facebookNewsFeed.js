(function runner(xpg, debug) {
  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */

  /**
   * @param {function(string, ?HTMLElement | ?Document)} cliXPG
   * @return {function(string, ): Array<HTMLElement>}
   */
  function maybePolyfillXPG(cliXPG) {
    if (
      typeof cliXPG !== 'function' ||
      cliXPG.toString().indexOf('[Command Line API]') === -1
    ) {
      return function(xpathQuery, startElem) {
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
    return cliXPG;
  }

  /**
   * @param {string} id
   * @returns {boolean}
   */
  function maybeRemoveElemById(id) {
    const elem = document.getElementById(id);
    let removed = false;
    if (elem) {
      elem.remove();
      removed = true;
    }
    return removed;
  }

  /**
   * @param {HTMLElement | Element | Node} elem
   * @param {string} [marker = 'wrvistited']
   */
  function markElemAsVisited(elem, marker = 'wrvistited') {
    if (elem != null) {
      elem.classList.add(marker);
    }
  }

  /**
   * @param {number} [delayTime = 3000]
   * @returns {Promise<void>}
   */
  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
    });
  }

  /**
   * @param {Element | HTMLElement | Node} elem - The element to be scrolled into view
   */
  function scrollIntoView(elem) {
    if (elem == null) return;
    elem.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
      inline: 'center'
    });
  }

  /**
   * @desc Scrolls the window by the supplied elements offsetTop. If the elements
   * offsetTop is zero then {@link scrollIntoView} is used
   * @param {Element | HTMLElement | Node} elem - The element who's offsetTop will be used to scroll by
   */
  function scrollToElemOffset(elem) {
    if (elem.offsetTop === 0) {
      return scrollIntoView(elem);
    }
    window.scrollTo({
      behavior: 'auto',
      left: 0,
      top: elem.offsetTop
    });
  }

  /**
   * @desc Scrolls the window by the supplied elements offsetTop. If the elements
   * offsetTop is zero then {@link scrollIntoView} is used
   * @param {Element | HTMLElement | Node} elem - The element who's offsetTop will be used to scroll by
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<void>}
   */
  function scrollToElemOffsetWithDelay(elem, delayTime = 1000) {
    scrollToElemOffset(elem);
    return delay(delayTime);
  }

  /**
   * @desc Determines if we can scroll any more
   * @return {boolean}
   */
  function canScrollMore() {
    return (
      window.scrollY + window.innerHeight <
      Math.max(
        document.body.scrollHeight,
        document.body.offsetHeight,
        document.documentElement.clientHeight,
        document.documentElement.scrollHeight,
        document.documentElement.offsetHeight
      )
    );
  }

  const outlinks = new Set();
  const goodSchemes = { 'http:': true, 'https:': true };
  const outLinkURLParser = new URL('about:blank');
  const outlinkSelector = 'a[href], area[href]';

  function shouldIgnoreLink(test) {
    let ignored = false;
    let i = ignored.length;
    while (i--) {
      if (test.startsWith(ignored[i])) {
        ignored = true;
        break;
      }
    }
    if (!ignored) {
      let parsed = true;
      try {
        outLinkURLParser.href = test;
      } catch (error) {
        parsed = false;
      }
      return !(parsed && goodSchemes[outLinkURLParser.protocol]);
    }
    return ignored;
  }

  function addOutLinks(toAdd) {
    let href;
    let i = toAdd.length;
    while (i--) {
      href = toAdd[i].href.trim();
      if (href && !outlinks.has(href) && !shouldIgnoreLink(href)) {
        outlinks.add(href);
      }
    }
  }

  function collectOutlinksFrom(queryFrom) {
    addOutLinks(queryFrom.querySelectorAll(outlinkSelector));
  }

  Object.defineProperty(window, '$wbOutlinks$', {
    get() {
      return Array.from(outlinks);
    },
    set() {},
    enumerable: false
  });

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
    '//div[starts-with(@id,"hyperfeed_story_id") and not(contains(@class, "wrvistited"))]';

  const scrollDelay = 1500;

  const removeAnnoyingElemId = 'pagelet_growth_expanding_cta';

  /**
   * @desc See description for {@link getFeedItems}
   * @param {HTMLElement} elem - The current
   * @returns {boolean}
   */
  function newsFeedItemFilter(elem) {
    return elem.offsetTop !== 0;
  }

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
  async function* makeIterator(xpathG) {
    const getFeedItems = query => xpathG(query).filter(newsFeedItemFilter);
    let feedItems = getFeedItems(feedItemSelector);
    let feedItem;
    do {
      while (feedItems.length > 0) {
        feedItem = feedItems.shift();
        await scrollToElemOffsetWithDelay(feedItem, scrollDelay);
        markElemAsVisited(feedItem);
        collectOutlinksFrom(feedItem);
        yield feedItem;
      }
      feedItems = getFeedItems(feedItemSelector);
      if (feedItems.length === 0) {
        await delay();
        feedItems = getFeedItems(feedItemSelector);
      }
    } while (feedItems.length > 0 && canScrollMore());
  }

  let removedAnnoying = maybeRemoveElemById(removeAnnoyingElemId);
  window.$WRNFIterator$ = makeIterator(maybePolyfillXPG(xpg));
  window.$WRIteratorHandler$ = async function() {
    if (!removedAnnoying) {
      removedAnnoying = maybeRemoveElemById(removeAnnoyingElemId);
    }
    const next = await $WRNFIterator$.next();
    return next.done;
  };
})($x, false);
