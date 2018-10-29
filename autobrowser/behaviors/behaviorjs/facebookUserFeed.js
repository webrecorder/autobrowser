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

  function addBehaviorStyle(styleDef) {
    if (document.getElementById('$wrStyle$') == null) {
      const style = document.createElement('style');
      style.id = '$wrStyle$';
      style.textContent = styleDef;
      document.head.appendChild(style);
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
   * @param {Element | HTMLElement | Node} elem - The element to be scrolled into view with delay
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<void>}
   */
  function scrollIntoViewWithDelay(elem, delayTime = 1000) {
    scrollIntoView(elem);
    return delay(delayTime);
  }

  /**
   * @param {Element | HTMLElement | Node} elem - The element to be
   */
  function scrollDownByElemHeight(elem) {
    if (!elem) return;
    const rect = elem.getBoundingClientRect();
    window.scrollBy(0, rect.height + elem.offsetHeight);
  }

  /**
   * @param {Element | HTMLElement | Node} elem - The element to be
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<void>}
   */
  function scrollDownByElemHeightWithDelay(elem, delayTime = 1000) {
    scrollDownByElemHeight(elem);
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

  /**
   * @desc Calls the click function on the supplied element if non-null/defined.
   * Returns true or false to indicate if the click happened
   * @param {HTMLElement | Element | Node} elem - The element to be clicked
   * @return {boolean}
   */
  function click(elem) {
    let clicked = false;
    if (elem != null) {
      elem.dispatchEvent(
        new window.MouseEvent('mouseover', {
          view: window,
          bubbles: true,
          cancelable: true
        })
      );
      elem.click();
      clicked = true;
    }
    return clicked;
  }

  /**
   * @param {HTMLElement | Element | Node} elem - The element to be clicked
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<boolean>}
   */
  async function clickWithDelay(elem, delayTime = 1000) {
    let clicked = click(elem);
    if (clicked) {
      await delay(delayTime);
    }
    return clicked;
  }

  /**
   * @param {HTMLElement | Element | Node} elem - The element to be
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<boolean>}
   */
  function scrollIntoViewAndClickWithDelay(elem, delayTime = 1000) {
    scrollIntoView(elem);
    return clickWithDelay(elem, delayTime);
  }

  class OutLinkCollector {
    constructor() {
      /**
       * @type {Set<string>}
       */
      this.outlinks = new Set();
      this.ignored = [
        'about:',
        'data:',
        'mailto:',
        'javascript:',
        'js:',
        '{',
        '*',
        'ftp:',
        'tel:'
      ];
      this.good = { 'http:': true, 'https:': true };
      this.urlParer = new URL('about:blank');
      this.outlinkSelector = 'a[href], area[href]';
    }

    shouldIgnore(test) {
      let ignored = false;
      let i = this.ignored.length;
      while (i--) {
        if (test.startsWith(this.ignored[i])) {
          ignored = true;
          break;
        }
      }
      if (!ignored) {
        let parsed = true;
        try {
          this.urlParer.href = test;
        } catch (error) {
          parsed = false;
        }
        return !(parsed && this.good[this.urlParer.protocol]);
      }
      return ignored;
    }

    collectFromDoc() {
      this.addOutLinks(document.querySelectorAll(this.outlinkSelector));
    }

    collectFrom(queryFrom) {
      this.addOutLinks(queryFrom.querySelectorAll(this.outlinkSelector));
    }

    addOutLinks(outlinks) {
      let href;
      let i = outlinks.length;
      while (i--) {
        href = outlinks[i].href.trim();
        if (href && !this.outlinks.has(href) && !this.shouldIgnore(href)) {
          this.outlinks.add(href);
        }
      }
    }

    /**
     * @param {HTMLAnchorElement|HTMLAreaElement|string} elemOrString
     */
    addOutlink(elemOrString) {
      const href = (elemOrString.href || elemOrString).trim();
      if (href && !this.outlinks.has(href) && !this.shouldIgnore(href)) {
        this.outlinks.add(href);
      }
    }

    /**
     * @return {string[]}
     */
    outLinkArray() {
      return Array.from(this.outlinks);
    }

    /**
     * @return {string[]}
     */
    toJSON() {
      return this.outLinkArray();
    }

    /**
     * @return {string[]}
     */
    valueOf() {
      return this.outLinkArray();
    }
  }

  const OLC = new OutLinkCollector();

  Object.defineProperty(window, '$wbOutlinks$', {
    value: OLC,
    writable: false,
    enumerable: false
  });

  addBehaviorStyle('.wr-debug-visited {border: 6px solid #3232F1;}');

  const userTimelineSelector =
    '//div[contains(@class, "userContentWrapper") and not(contains(@class, "wrvistited"))]';

  const moreReplies = 'a[role="button"].UFIPagerLink';
  const repliesToRepliesA = 'a[role="button"].UFICommentLink';

  const removeAnnoyingElemId = 'pagelet_growth_expanding_cta';
  const delayTime = 1500;
  const loadDelayTime = 3000;

  async function* clickRepliesToReplies(tlItem) {
    let rToR = tlItem.querySelectorAll(repliesToRepliesA);
    let i = 0;
    let length = rToR.length;
    let rtr;
    while (i < length) {
      rtr = rToR[i];
      if (debug) rtr.classList.add('wr-debug-visited');
      await scrollIntoViewAndClickWithDelay(rtr, delayTime);
      yield rtr;
      i += 1;
    }
    rToR = tlItem.querySelectorAll(repliesToRepliesA);
    if (rToR.length) {
      i = 0;
      length = rToR.length;
      while (i < length) {
        rtr = rToR[i];
        if (debug) rtr.classList.add('wr-debug-visited');
        await scrollIntoViewAndClickWithDelay(rtr, delayTime);
        yield rToR;
        i += 1;
      }
    }
  }

  async function* makeIterator(xpathGenerator) {
    let timelineItems = xpathGenerator(userTimelineSelector);
    let tlItem;
    let replies;
    do {
      while (timelineItems.length > 0) {
        tlItem = timelineItems.shift();
        if (debug) tlItem.classList.add('wr-debug-visited');
        await scrollIntoViewWithDelay(tlItem, delayTime);
        markElemAsVisited(tlItem);
        OLC.collectFrom(tlItem);
        yield tlItem;
        replies = tlItem.querySelector(moreReplies);
        if (replies) {
          if (debug) replies.classList.add('wr-debug-visited');
          await scrollIntoViewAndClickWithDelay(replies, delayTime);
          yield replies;
        }
        yield* clickRepliesToReplies(tlItem);
      }
      timelineItems = xpathGenerator(userTimelineSelector);
      if (timelineItems.length === 0) {
        await scrollDownByElemHeightWithDelay(tlItem, loadDelayTime);
        timelineItems = xpathGenerator(userTimelineSelector);
      }
    } while (timelineItems.length > 0 && canScrollMore());
  }

  let removedAnnoying = maybeRemoveElemById(removeAnnoyingElemId);
  window.$WRTLIterator$ = makeIterator(maybePolyfillXPG(xpg));
  window.$WRIteratorHandler$ = async function() {
    if (!removedAnnoying) {
      removedAnnoying = maybeRemoveElemById(removeAnnoyingElemId);
    }
    const next = await $WRTLIterator$.next();
    return next.done;
  };
})($x, false);
