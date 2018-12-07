(function runner(xpg, debug) {
  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */
  function xpathSnapShot(xpathQuery, startElem) {
    if (startElem == null) {
      startElem = document;
    }
    return document.evaluate(
      xpathQuery,
      startElem,
      null,
      XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
      null
    );
  }

  /**
   * @param {string} selector - the selector to be use
   * @param {Element|Node|HTMLElement|Document} [context] - element to use rather than document for the querySelector call
   * @returns {Element | Node | HTMLElement | HTMLIFrameElement}
   */
  function qs(selector, context) {
    if (context != null) return context.querySelector(selector);
    return document.querySelector(selector);
  }

  /**
   * @param {string} eid
   * @param {?Document} [context]
   * @returns {?HTMLElement}
   */
  function id(eid, context) {
    if (context != null) return context.getElementById(eid);
    return document.getElementById(eid);
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
   * @param {?Element|?Node} elem
   * @param {string} clazz
   */
  function addClass(elem, clazz) {
    if (elem) {
      elem.classList.add(clazz);
    }
  }

  /**
   * @param {?Element|?Node} elem
   * @param {string} clazz
   */
  function removeClass(elem, clazz) {
    if (elem) {
      elem.classList.remove(clazz);
    }
  }

  /**
   * @param {?Element} elem
   * @param {string} clazz
   * @return {boolean}
   */
  function hasClass(elem, clazz) {
    if (elem) return elem.classList.contains(clazz);
    return false;
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
   * @desc Returns a promise that resolves when the supplied predicate function
   * returns a truthy value. Polling via setInterval 1sec.
   * @param {function(): boolean} predicate
   * @return {Promise<void>}
   */
  function waitForPredicate(predicate) {
    return new Promise(resolve => {
      let int = setInterval(() => {
        if (predicate()) {
          clearInterval(int);
          resolve();
        }
      }, 1000);
    });
  }

  /**
   * @param {Element} parentElement
   * @param {number} currentChildCount
   * @param {{pollRate: number, max: number}} [opts]
   * @return {Promise<void>}
   */
  function waitForAdditionalElemChildren(
    parentElement,
    currentChildCount,
    opts
  ) {
    let pollRate = 1000;
    let max = 6;
    if (opts != null) {
      if (opts.pollRate != null) pollRate = opts.pollRate;
      if (opts.max != null) max = opts.max;
    }
    let n = 0;
    let int = -1;
    return new Promise(resolve => {
      int = setInterval(() => {
        if (!parentElement.isConnected) {
          clearInterval(int);
          return resolve();
        }
        if (
          parentElement.children &&
          parentElement.children.length > currentChildCount
        ) {
          clearInterval(int);
          return resolve();
        }
        if (n > max) {
          clearInterval(int);
          return resolve();
        }
        n += 1;
      }, pollRate);
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

  if (typeof window.$wbOutlinkSet$ === 'undefined') {
    Object.defineProperty(window, '$wbOutlinkSet$', {
      value: new Set(),
      enumerable: false
    });
  } else {
    window.$wbOutlinkSet$.clear();
  }

  if (typeof window.$wbOutlinks$ === 'undefined') {
    Object.defineProperty(window, '$wbOutlinks$', {
      get() {
        return Array.from(window.$wbOutlinkSet$);
      },
      set() {},
      enumerable: false
    });
  }

  const outlinks = window.$wbOutlinkSet$;
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
   * @param {Element | Node | HTMLElement} selectFrom - element to use for the querySelector call
   * @param {string} selector - the css selector to use
   * @returns {boolean}
   */
  function selectElemFromAndClick(selectFrom, selector) {
    return click(selectFrom.querySelector(selector));
  }

  /**
   * @param {Element | Node | HTMLElement} elem - the element to be clicked
   * @param {function(): boolean} predicate - function returning true or false indicating the wait condition is satisfied
   * @returns {Promise<boolean>}
   */
  async function clickAndWaitFor(elem, predicate) {
    const clicked = click(elem);
    if (clicked) {
      await waitForPredicate(predicate);
    }
    return clicked;
  }

  const selectors = {
    tweetStreamContainer: 'div.stream-container',
    tweetStreamDiv: 'div.stream',
    tweetInStreamContent: 'div.content',
    tweetStreamItems: 'ol.stream-items',
    tweetFooterSelector: 'div.stream-item-footer',
    replyActionSelector: 'div.ProfileTweet-action--reply',
    noReplySpanSelector: 'span.ProfileTweet-actionCount--isZero',
    replyBtnSelector: 'button[data-modal="ProfileTweet-reply"]',
    closeFullTweetSelector: 'div.PermalinkProfile-dismiss > span',
    threadSelector: 'a.js-nav.show-thread-link',
    userProfileInStream: 'AdaptiveStreamUserGallery-user',
    userProfileContent: 'div.AdaptiveStreamUserGallery-user',
    showMoreInThread: 'button.ThreadedConversation-showMoreThreadsButton',
    tweetPermalinkContainer: 'div.permalink-container',
    tweetPermalinkRepliesContainer: 'ol.stream-items',
    threadedConvMoreReplies: 'a.ThreadedConversation-moreRepliesLink'
  };

  const elemIds = {
    permalinkOverlay: 'permalink-overlay'
  };

  /**
   * @desc Xpath query used to traverse each tweet within a timeline.
   *
   * During visiting tweets, the tweets are marked as visited by adding the
   * sentinel`$wrvisited$` to the classList of a tweet seen during timeline traversal,
   * normal usage of a CSS selector and `document.querySelectorAll` is impossible
   * unless significant effort is made in order to ensure each tweet is seen only
   * once during timeline traversal.
   *
   * Tweets in a timeline have the following structure:
   *  div.tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.dismissible-content...
   *    |- div.content
   *       |- ...
   *  div.tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.dismissible-content...
   *   |- div.content
   *      |- ...
   *
   * We care only about the minimal identifiable markers of a tweet:
   *  div.tweet.js-stream-tweet...
   *   |- div.content
   *
   * such that when a tweet is visited during timeline traversal it becomes:
   *  div.tweet.js-stream-tweet...
   *   |- div.content.wrvistited
   *
   * which invalidates the query on subsequent evaluations against the DOM,
   * thus allowing for unique traversal of each tweet in a timeline.
   * @type {string}
   */
  const tweetXpath =
    '//div[starts-with(@class,"tweet js-stream-tweet")]/div[@class="content" and not(contains(@class, "wrvistited"))]';

  const threadedTweetXpath =
    '//div[@id="permalink-overlay"]//div[starts-with(@class,"tweet permalink-tweet") and not(contains(@class, "wrvistited"))]';

  /**
   * @desc A variation of {@link tweetXpath} in that it is further constrained
   * to only search tweets within the overlay that appears when you click on
   * a tweet
   * @type {string}
   */
  const overlayTweetXpath = `//div[@id="permalink-overlay"]${tweetXpath}`;

  addBehaviorStyle(
    '.wr-debug-visited {border: 6px solid #3232F1;} .wr-debug-visited-thread-reply {border: 6px solid green;} .wr-debug-visited-overlay {border: 6px solid pink;} .wr-debug-click {border: 6px solid red;}'
  );

  // const logger = getNoneNukedConsole();

  /**
   * @desc Clicks (views) the currently visited tweet
   * @param {HTMLElement|Element} tweetContainer
   * @return {Promise<?Element>}
   */
  async function openTweet(tweetContainer) {
    const permalinkPath = tweetContainer.dataset.permalinkPath;
    // logger.log(`tweet has perlinkPath = ${permalinkPath}`);
    const wasClicked = await clickAndWaitFor(tweetContainer, () =>
      document.baseURI.endsWith(permalinkPath)
    );
    if (wasClicked) {
      // the overlay was opened
      const fullTweetOverlay = id(elemIds.permalinkOverlay);
      if (debug) {
        addClass(fullTweetOverlay, 'wr-debug-visited-overlay');
      }
      return fullTweetOverlay;
    }
    return null;
  }

  /**
   * @desc Closes the overlay representing viewing a tweet
   * @return {Promise<boolean>}
   */
  async function closeTweetOverlay(originalBaseURI) {
    const overlay = qs(selectors.closeFullTweetSelector);
    if (!overlay) return Promise.resolve(false);
    if (debug) addClass(overlay, 'wr-debug-click');
    return clickAndWaitFor(overlay, () => {
      const done = document.baseURI === originalBaseURI;
      if (done && debug) {
        removeClass(overlay, 'wr-debug-click');
      }
      return done;
    });
  }

  async function* vistReplies(fullTweetOverlay) {
    let snapShot = xpathSnapShot(overlayTweetXpath, fullTweetOverlay);
    let aTweet;
    let i, len;
    // logger.log(`we have ${snapShot.snapshotLength} replies`);
    if (snapShot.snapshotLength === 0) return;
    do {
      len = snapShot.snapshotLength;
      i = 0;
      while (i < len) {
        aTweet = snapShot.snapshotItem(i);
        // logger.log('visting reply or thread tweet', aTweet);
        markElemAsVisited(aTweet);
        collectOutlinksFrom(aTweet);
        if (debug) {
          addClass(aTweet, 'wr-debug-visited-thread-reply');
        }
        await scrollIntoViewWithDelay(aTweet);
        yield false;
        i += 1;
      }
      snapShot = xpathSnapShot(overlayTweetXpath, fullTweetOverlay);
      if (snapShot.snapshotLength === 0) {
        if (
          selectElemFromAndClick(fullTweetOverlay, selectors.showMoreInThread)
        ) {
          await delay();
        }
        snapShot = xpathSnapShot(overlayTweetXpath, fullTweetOverlay);
      }
    } while (snapShot.snapshotLength > 0);
  }

  async function* vistThreadedTweet(fullTweetOverlay) {
    // logger.log('in vistThreadedTweet', fullTweetOverlay);
    // logger.log('visiting tweets that are apart of the thread');
    let snapShot = xpathSnapShot(threadedTweetXpath, fullTweetOverlay);
    let aTweet;
    let i, len;
    // logger.log(`we have ${snapShot.snapshotLength} replies`);
    if (snapShot.snapshotLength === 0) return;
    do {
      len = snapShot.snapshotLength;
      i = 0;
      while (i < len) {
        aTweet = snapShot.snapshotItem(i);
        // logger.log('visting reply or thread tweet', aTweet);
        markElemAsVisited(aTweet);
        collectOutlinksFrom(aTweet);
        if (debug) {
          addClass(aTweet, 'wr-debug-visited-thread-reply');
        }
        await scrollIntoViewWithDelay(aTweet);
        yield false;
        i += 1;
      }
      snapShot = xpathSnapShot(threadedTweetXpath, fullTweetOverlay);
      if (snapShot.snapshotLength === 0) {
        if (
          selectElemFromAndClick(
            fullTweetOverlay,
            selectors.threadedConvMoreReplies
          )
        ) {
          await delay();
        }
        snapShot = xpathSnapShot(threadedTweetXpath, fullTweetOverlay);
      }
    } while (snapShot.snapshotLength > 0);
  }

  function hasVideo(tweet) {
    const videoContainer = tweet.querySelector(
      'div.AdaptiveMedia-videoContainer'
    );
    if (videoContainer != null) {
      const video = videoContainer.querySelector('video');
      if (video) {
        video.play();
      }
      return true;
    }
    return false;
  }

  /**
   * @param {HTMLLIElement | Element} tweetStreamLI
   * @param {string} originalBaseURI
   * @return {AsyncIterator<boolean>}
   */
  async function* handleTweet(tweetStreamLI, originalBaseURI) {
    const notTweet = hasClass(tweetStreamLI, selectors.userProfileInStream);
    if (notTweet) {
      if (debug) {
        addClass(tweetStreamLI, 'wr-debug-visited');
      }
      collectOutlinksFrom(tweetStreamLI);
      await scrollIntoViewWithDelay(tweetStreamLI);
      yield false;
      return;
    }

    const streamTweetDiv = tweetStreamLI.firstElementChild;
    const tweetContent = qs(selectors.tweetInStreamContent, streamTweetDiv);
    // logger.log('Tweet content', tweetContent);
    if (debug) {
      addClass(streamTweetDiv, 'wr-debug-visited');
    }

    if (hasVideo(tweetStreamLI)) {
      yield true;
    }
    const footer = qs(selectors.tweetFooterSelector, tweetContent);
    const replyAction = qs(selectors.replyActionSelector, footer);
    const replyButton = qs(selectors.replyBtnSelector, replyAction);

    const hasReplies = qs(selectors.noReplySpanSelector, replyButton) == null;
    const apartOfThread = qs(selectors.threadSelector, tweetContent) != null;

    await scrollIntoViewWithDelay(tweetContent);
    collectOutlinksFrom(tweetContent);
    // yield tweet;
    // logger.log('opening tweet overlay');
    const tweetPermalinkOverlay = await openTweet(streamTweetDiv);
    // logger.log(tweetPermalinkOverlay);
    // logger.log('opened tweet');
    if (hasReplies) {
      // logger.log('visiting replies');
      yield* vistReplies(tweetPermalinkOverlay);
    } else if (apartOfThread) {
      yield* vistThreadedTweet(tweetPermalinkOverlay);
    } else {
      collectOutlinksFrom(tweetPermalinkOverlay);
      yield false;
    }
    // logger.log('closing tweet overlay');
    await closeTweetOverlay(originalBaseURI);
  }
  /**
   * @param originalBaseURI
   * @return {AsyncIterableIterator<boolean>}
   */
  async function* hashTagIterator(originalBaseURI) {
    const streamItems = qs(selectors.tweetStreamItems);
    let tweetLI = streamItems.firstElementChild;
    let numLoadedTweets = streamItems.children.length;
    while (tweetLI != null) {
      markElemAsVisited(tweetLI);
      if (tweetLI.getBoundingClientRect().height !== 0) {
        if (hasClass(tweetLI, 'AdaptiveSearchTimeline-separationModule')) {
          await scrollIntoViewWithDelay(tweetLI);
          collectOutlinksFrom(tweetLI);
          yield false;
        } else {
          yield* handleTweet(tweetLI, originalBaseURI);
        }
      }
      numLoadedTweets = streamItems.children.length;
      if (tweetLI.nextElementSibling == null) {
        // logger.log('waiting for more tweets');
        await waitForAdditionalElemChildren(streamItems, numLoadedTweets);
      }
      // logger.log('getting next tweet');
      tweetLI = tweetLI.nextElementSibling;
    }
  }
  /**
   * @type {AsyncIterator<boolean>}
   */
  window.$WRTweetIterator$ = hashTagIterator(document.baseURI);
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRTweetIterator$.next();
    return { done: next.done, wait: !!next.value };
  };
  //
  // async function run() {
  //   for await (const tweet of window.$WRTweetIterator$) {
  //     logger.log(tweet);
  //   }
  // }
  //
  // run().catch(error => console.error(error));
})($x, true);
